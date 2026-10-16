import sys
import unittest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from fastapi import HTTPException

sys.path.insert(0, r"d:\Disaster_OS_Phase2\multi_agent_disaster_management\Multi-Agent-System")

from app import app, require_admin, get_current_user, ws_manager, is_trusted_origin, TRUSTED_ORIGINS
from starlette.websockets import WebSocketDisconnect
from database import (
    init_db,
    get_connection,
    create_session,
    revoke_session,
    hash_password,
)


class TestAuthenticationSecurity(unittest.TestCase):
    def get_client(self):
        return TestClient(app)

    def test_valid_login_operator(self):
        client = self.get_client()
        res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], "operator@disaster.local")
        self.assertEqual(data["user"]["role"], "operator")
        self.assertIn("disaster_os_session", res.cookies)

    def test_valid_login_admin(self):
        client = self.get_client()
        res = client.post("/api/auth/login", json={
            "email": "admin@disaster.local",
            "password": "admin123",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["role"], "admin")

    def test_invalid_password(self):
        client = self.get_client()
        res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "wrong_password_999",
        })
        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("Invalid email or password", data["message"])

    def test_invalid_email(self):
        client = self.get_client()
        res = client.post("/api/auth/login", json={
            "email": "nonexistent_user@unknown.domain",
            "password": "some_password",
        })
        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("Invalid email or password", data["message"])

    def test_random_credentials(self):
        client = self.get_client()
        res = client.post("/api/auth/login", json={
            "email": "' OR 1=1 --",
            "password": "random_payload",
        })
        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertEqual(data["status"], "error")

    def test_protected_endpoint_without_token(self):
        client = self.get_client()
        res = client.get("/api/runs")
        self.assertEqual(res.status_code, 401)

    def test_protected_endpoint_with_bearer_token(self):
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        token = login_res.json()["token"]

        unauth_client = self.get_client()
        res = unauth_client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("runs", res.json())

    def test_protected_endpoint_with_cookie(self):
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        cookie_val = login_res.cookies.get("disaster_os_session")

        unauth_client = self.get_client()
        unauth_client.cookies.set("disaster_os_session", cookie_val)
        res = unauth_client.get("/api/runs")
        self.assertEqual(res.status_code, 200)

    def test_auth_me_endpoint(self):
        client = self.get_client()
        res = client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)

        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        token = login_res.json()["token"]

        unauth_client = self.get_client()
        res2 = unauth_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["user"]["email"], "operator@disaster.local")

    def test_logout_invalidates_session(self):
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        token = login_res.json()["token"]

        # Access with bearer
        unauth_client = self.get_client()
        res_before = unauth_client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_before.status_code, 200)

        # Logout
        logout_res = unauth_client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # Verify token revoked
        res_after = unauth_client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_after.status_code, 401)

    def test_expired_session_rejected(self):
        expired_dt = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("expired_test_token_123", 1, expired_dt),
        )
        conn.commit()
        conn.close()

        client = self.get_client()
        res = client.get("/api/runs", headers={"Authorization": "Bearer expired_test_token_123"})
        self.assertEqual(res.status_code, 401)


class TestAdministratorAuthorization(unittest.TestCase):
    def setUp(self):
        init_db()
        self._cleanup_test_users()

    def tearDown(self):
        self._cleanup_test_users()

    def _cleanup_test_users(self):
        conn = get_connection()
        conn.execute("DELETE FROM sessions WHERE user_id > 2")
        conn.execute("DELETE FROM users WHERE user_id > 2")
        conn.commit()
        conn.close()

    def get_client(self):
        return TestClient(app)

    def _login(self, email, password):
        client = self.get_client()
        res = client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(res.status_code, 200)
        return res.json()["token"]

    def get_operator_token(self):
        return self._login("operator@disaster.local", "operator123")

    def get_admin_token(self):
        return self._login("admin@disaster.local", "admin123")

    def test_require_admin_dependency_unit(self):
        """Unit test the require_admin dependency directly."""
        admin_user = {"user_id": 2, "name": "Admin", "email": "admin@disaster.local", "role": "admin"}
        self.assertEqual(require_admin(current_user=admin_user), admin_user)

        operator_user = {"user_id": 1, "name": "Operator", "email": "operator@disaster.local", "role": "operator"}
        with self.assertRaises(HTTPException) as ctx:
            require_admin(current_user=operator_user)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Administrative privileges required", ctx.exception.detail)

    def test_unauthenticated_requests_cannot_access_admin_endpoints(self):
        """Unauthenticated requests to every admin endpoint receive HTTP 401."""
        client = self.get_client()
        endpoints = [
            ("GET", "/api/admin/users", None),
            ("DELETE", "/api/admin/users/999", None),
            ("PUT", "/api/admin/users/1/role", {"role": "admin"}),
            ("GET", "/api/admin/config", None),
            ("POST", "/api/admin/config", {"key": "val"}),
            ("POST", "/api/auth/register", {"name": "Anon", "email": "anon@test.local", "password": "pass"}),
        ]
        for method, path, payload in endpoints:
            with self.subTest(method=method, path=path):
                if method == "GET":
                    res = client.get(path)
                elif method == "DELETE":
                    res = client.delete(path)
                elif method == "PUT":
                    res = client.put(path, json=payload)
                elif method == "POST":
                    res = client.post(path, json=payload)
                self.assertEqual(res.status_code, 401, f"{method} {path} should return 401 for unauthenticated requests")

    def test_authenticated_operator_blocked_with_403_on_admin_endpoints(self):
        """Authenticated operators receive HTTP 403 on every admin endpoint."""
        token = self.get_operator_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        endpoints = [
            ("GET", "/api/admin/users", None),
            ("DELETE", "/api/admin/users/2", None),
            ("PUT", "/api/admin/users/1/role", {"role": "admin"}),
            ("GET", "/api/admin/config", None),
            ("POST", "/api/admin/config", {"key": "val"}),
        ]
        for method, path, payload in endpoints:
            with self.subTest(method=method, path=path):
                if method == "GET":
                    res = client.get(path, headers=headers)
                elif method == "DELETE":
                    res = client.delete(path, headers=headers)
                elif method == "PUT":
                    res = client.put(path, json=payload, headers=headers)
                elif method == "POST":
                    res = client.post(path, json=payload, headers=headers)
                self.assertEqual(res.status_code, 403, f"{method} {path} should return 403 for operator")

    def test_authenticated_operator_via_cookie_blocked_with_403(self):
        """Authenticated operator using session cookie receives HTTP 403 on admin endpoints."""
        token = self.get_operator_token()
        client = self.get_client()
        client.cookies.set("disaster_os_session", token)

        res = client.get("/api/admin/users")
        self.assertEqual(res.status_code, 403)

        res = client.get("/api/admin/config")
        self.assertEqual(res.status_code, 403)

    def test_administrator_retains_legitimate_access(self):
        """Administrators have full authorized access to admin endpoints."""
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        # Admin can list users
        res = client.get("/api/admin/users", headers=headers)
        self.assertEqual(res.status_code, 200)
        users = res.json().get("users", [])
        self.assertTrue(any(u["email"] == "admin@disaster.local" for u in users))

        # Admin can get config
        res = client.get("/api/admin/config", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), dict)

        # Admin can update config
        res = client.post("/api/admin/config", json={"test_security_param": "secured"}, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

        # Verify config was updated
        res = client.get("/api/admin/config", headers=headers)
        self.assertEqual(res.json().get("test_security_param"), "secured")

    def test_operator_cannot_create_admin_account_through_registration(self):
        """Operators cannot register accounts with admin privileges."""
        token = self.get_operator_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        # Operator attempts to register an admin user
        res = client.post(
            "/api/auth/register",
            json={
                "name": "Attacker Admin",
                "email": "attacker_admin@disaster.local",
                "password": "attack_password123",
                "role": "admin",
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 403)

        # Verify user was not created in database
        conn = get_connection()
        row = conn.execute("SELECT * FROM users WHERE email = 'attacker_admin@disaster.local'").fetchone()
        conn.close()
        self.assertIsNone(row, "Attacker admin user must not be present in the database")

        # Operator attempts with uppercase and whitespace role variants
        for variant in ("ADMIN", " Admin ", "administrator", "Administrator"):
            with self.subTest(variant=variant):
                res = client.post(
                    "/api/auth/register",
                    json={
                        "name": "Attacker Admin",
                        "email": f"attacker_{variant.strip().lower()}@disaster.local",
                        "password": "attack_password123",
                        "role": variant,
                    },
                    headers=headers,
                )
                self.assertEqual(res.status_code, 403)

    def test_operator_untrusted_role_forced_to_operator(self):
        """Non-admin cannot supply an arbitrary role to elevate privileges."""
        token = self.get_operator_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        res = client.post(
            "/api/auth/register",
            json={
                "name": "Custom Role User",
                "email": "custom_role_user@disaster.local",
                "password": "user_password123",
                "role": "superuser",
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)

        conn = get_connection()
        row = conn.execute("SELECT role FROM users WHERE email = 'custom_role_user@disaster.local'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["role"], "operator", "Untrusted role must default to operator")

    def test_operator_legitimate_registration(self):
        """Operators can legitimately register new operator accounts."""
        token = self.get_operator_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        res = client.post(
            "/api/auth/register",
            json={
                "name": "Legit Field Operator",
                "email": "legit_operator@disaster.local",
                "password": "secure_operator_pass",
                "role": "operator",
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("user_id", data)

        conn = get_connection()
        row = conn.execute("SELECT role FROM users WHERE email = 'legit_operator@disaster.local'").fetchone()
        conn.close()
        self.assertEqual(row["role"], "operator")

    def test_administrator_can_register_admin_and_operator(self):
        """Administrators can register both admin and operator accounts."""
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        # Admin creates another admin
        res = client.post(
            "/api/auth/register",
            json={
                "name": "Co-Admin",
                "email": "co_admin@disaster.local",
                "password": "co_admin_password",
                "role": "admin",
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

        conn = get_connection()
        admin_row = conn.execute("SELECT role FROM users WHERE email = 'co_admin@disaster.local'").fetchone()
        self.assertEqual(admin_row["role"], "admin")

        # Admin creates an operator
        res_op = client.post(
            "/api/auth/register",
            json={
                "name": "Admin Created Op",
                "email": "admin_created_op@disaster.local",
                "password": "admin_op_password",
                "role": "operator",
            },
            headers=headers,
        )
        self.assertEqual(res_op.status_code, 200)
        self.assertEqual(res_op.json()["status"], "success")

        op_row = conn.execute("SELECT role FROM users WHERE email = 'admin_created_op@disaster.local'").fetchone()
        conn.close()
        self.assertEqual(op_row["role"], "operator")

    def test_administrator_can_manage_roles_and_delete_users(self):
        """Administrators can change user roles and delete users."""
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        # First register a user
        res = client.post(
            "/api/auth/register",
            json={
                "name": "Managed User",
                "email": "managed_user@disaster.local",
                "password": "managed_password",
                "role": "operator",
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        user_id = res.json()["user_id"]

        # Admin promotes user to admin
        res = client.put(f"/api/admin/users/{user_id}/role", json={"role": "admin"}, headers=headers)
        self.assertEqual(res.status_code, 200)

        conn = get_connection()
        row = conn.execute("SELECT role FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
        self.assertEqual(row["role"], "admin")

        # Admin deletes user
        res = client.delete(f"/api/admin/users/{user_id}", headers=headers)
        self.assertEqual(res.status_code, 200)

        conn = get_connection()
        deleted_row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
        self.assertIsNone(deleted_row)


class TestStateChangingEndpointsAuthentication(unittest.TestCase):
    def setUp(self):
        init_db()

    def get_client(self):
        return TestClient(app)

    def get_operator_token(self):
        client = self.get_client()
        res = client.post("/api/auth/login", json={"email": "operator@disaster.local", "password": "operator123"})
        self.assertEqual(res.status_code, 200)
        return res.json()["token"]

    def test_unauthenticated_state_changing_endpoints_return_401(self):
        """Unauthenticated requests to all state-changing endpoints receive HTTP 401."""
        client = self.get_client()
        endpoints = [
            ("POST", "/api/impact/assess", {
                "latitude": 19.076,
                "longitude": 72.877,
                "disaster_type": "earthquake",
                "magnitude": 6.0,
            }),
            ("POST", "/api/corridors/plan", {
                "origin_lat": 19.076,
                "origin_lng": 72.878,
                "dest_lat": 19.120,
                "dest_lng": 72.900,
            }),
            ("POST", "/api/routes/plan", {
                "start_lat": 19.076,
                "start_lng": 72.878,
                "end_lat": 19.120,
                "end_lng": 72.900,
            }),
            ("POST", "/api/intelligence/correlate", None),
            ("POST", "/api/intelligence/status/refresh", None),
        ]
        for method, path, payload in endpoints:
            with self.subTest(path=path):
                res = client.post(path, json=payload)
                self.assertEqual(res.status_code, 401, f"{path} must return 401 for unauthenticated requests")

    def test_authenticated_operator_can_use_state_changing_endpoints(self):
        """Authenticated operators can successfully execute all 5 state-changing endpoints."""
        token = self.get_operator_token()
        headers = {"Authorization": f"Bearer {token}"}
        client = self.get_client()

        # 1. POST /api/impact/assess
        res = client.post(
            "/api/impact/assess",
            json={
                "latitude": 19.076,
                "longitude": 72.877,
                "disaster_type": "flood",
                "rainfall_mm": 50.0,
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("assessment", data)

        # 2. POST /api/corridors/plan
        res = client.post(
            "/api/corridors/plan",
            json={
                "origin_lat": 19.076,
                "origin_lng": 72.878,
                "dest_lat": 19.120,
                "dest_lng": 72.900,
                "profile": "car",
                "population_to_evacuate": 250,
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("corridor", data)

        # 3. POST /api/routes/plan
        res = client.post(
            "/api/routes/plan",
            json={
                "start_lat": 19.076,
                "start_lng": 72.878,
                "end_lat": 19.120,
                "end_lng": 72.900,
            },
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("route", data)

        # 4. POST /api/intelligence/correlate
        res = client.post("/api/intelligence/correlate", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("compound_events", data)

        # 5. POST /api/intelligence/status/refresh
        res = client.post("/api/intelligence/status/refresh", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("sources", data)


class TestWebSocketAuthenticationSecurity(unittest.TestCase):
    def get_client(self):
        return TestClient(app)

    def test_ws_unauthenticated_connection_rejected(self):
        client = self.get_client()
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with client.websocket_connect("/ws/simulation") as ws:
                pass
        self.assertEqual(ctx.exception.code, 1008)
        self.assertEqual(len(ws_manager.active_connections), 0)

    def test_ws_invalid_session_rejected(self):
        client = self.get_client()
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with client.websocket_connect("/ws/simulation", cookies={"disaster_os_session": "invalid_forged_token_xyz"}) as ws:
                pass
        self.assertEqual(ctx.exception.code, 1008)
        self.assertEqual(len(ws_manager.active_connections), 0)

    def test_ws_expired_session_rejected_and_revoked(self):
        client = self.get_client()
        # Create an expired session in DB
        expired_token = create_session(1, duration_hours=24)
        past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn = get_connection()
        conn.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (past_time, expired_token))
        conn.commit()
        conn.close()

        with self.assertRaises(WebSocketDisconnect) as ctx:
            with client.websocket_connect("/ws/simulation", cookies={"disaster_os_session": expired_token}) as ws:
                pass
        self.assertEqual(ctx.exception.code, 1008)
        self.assertEqual(len(ws_manager.active_connections), 0)

        # Verify session was revoked from SQLite
        conn = get_connection()
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (expired_token,)).fetchone()
        conn.close()
        self.assertIsNone(row, "Expired session record should have been pruned/revoked")

    def test_ws_authenticated_via_cookie_accepted(self):
        client = self.get_client()
        # Login to obtain valid session cookie
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        cookie_client = self.get_client()
        cookie_client.cookies.set("disaster_os_session", token)

        initial_count = len(ws_manager.active_connections)
        with cookie_client.websocket_connect("/ws/simulation") as ws:
            self.assertEqual(len(ws_manager.active_connections), initial_count + 1)
            # Send test broadcast
            test_event = {"type": "STATE_TRANSITION", "stage": "ANALYSIS"}
            import asyncio
            asyncio.run(ws_manager.broadcast(test_event))
            msg = ws.receive_json()
            self.assertEqual(msg["type"], "STATE_TRANSITION")
            self.assertEqual(msg["stage"], "ANALYSIS")

        # After disconnect, socket is removed from active connections
        self.assertEqual(len(ws_manager.active_connections), initial_count)

    def test_ws_authenticated_via_bearer_header_accepted(self):
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        # Use fresh client without cookies to verify pure Bearer header authentication
        bearer_client = self.get_client()
        initial_count = len(ws_manager.active_connections)
        with bearer_client.websocket_connect("/ws/simulation", headers={"Authorization": f"Bearer {token}"}) as ws:
            self.assertEqual(len(ws_manager.active_connections), initial_count + 1)
            test_event = {"type": "VEHICLE_DISPATCH", "resource_id": "RES-01"}
            import asyncio
            asyncio.run(ws_manager.broadcast(test_event))
            msg = ws.receive_json()
            self.assertEqual(msg["type"], "VEHICLE_DISPATCH")
            self.assertEqual(msg["resource_id"], "RES-01")

        self.assertEqual(len(ws_manager.active_connections), initial_count)

    def test_ws_query_string_token_rejected(self):
        """Tokens passed via query string must be rejected (forbidden per security policy)."""
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        token = login_res.json()["token"]

        # Ensure no cookie is passed so token is only in the query string
        qs_client = self.get_client()
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with qs_client.websocket_connect(f"/ws/simulation?token={token}") as ws:
                pass
        self.assertEqual(ctx.exception.code, 1008)
        self.assertEqual(len(ws_manager.active_connections), 0)

    def test_ws_unauthorized_clients_receive_no_broadcasts(self):
        """Verify rejected clients never receive broadcast data and active_connections is protected."""
        client = self.get_client()
        with self.assertRaises(WebSocketDisconnect):
            with client.websocket_connect("/ws/simulation") as ws:
                pass

        self.assertEqual(len(ws_manager.active_connections), 0)
        # Broadcast confidential data
        confidential_data = {"type": "SECRET_TRIAGE_UPDATE", "triage_score": 98.5}
        import asyncio
        asyncio.run(ws_manager.broadcast(confidential_data))
        # Ensure no active connection received or stored it
        self.assertEqual(len(ws_manager.active_connections), 0)

    def test_ws_trusted_origin_with_valid_authentication(self):
        """Valid session from a trusted origin (e.g. http://localhost:3000) connects successfully."""
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        ws_client = self.get_client()
        ws_client.cookies.set("disaster_os_session", token)

        initial_count = len(ws_manager.active_connections)
        with ws_client.websocket_connect(
            "/ws/simulation",
            headers={"Origin": "http://localhost:3000"},
        ) as ws:
            self.assertEqual(len(ws_manager.active_connections), initial_count + 1)
            test_event = {"type": "TRUSTED_ORIGIN_EVENT", "status": "OK"}
            import asyncio
            asyncio.run(ws_manager.broadcast(test_event))
            msg = ws.receive_json()
            self.assertEqual(msg["type"], "TRUSTED_ORIGIN_EVENT")

        self.assertEqual(len(ws_manager.active_connections), initial_count)

    def test_ws_untrusted_origin_with_valid_authentication_rejected(self):
        """Cross-Site WebSocket Hijacking prevention: valid session from untrusted origin is rejected."""
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        ws_client = self.get_client()
        ws_client.cookies.set("disaster_os_session", token)

        initial_count = len(ws_manager.active_connections)
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with ws_client.websocket_connect(
                "/ws/simulation",
                headers={"Origin": "https://evil-hacker-site.com"},
            ) as ws:
                pass
        self.assertEqual(ctx.exception.code, 1008)
        self.assertEqual(len(ws_manager.active_connections), initial_count)

        # Ensure no broadcasts leak to untrusted origin
        import asyncio
        asyncio.run(ws_manager.broadcast({"type": "SECRET_DATA", "val": 42}))
        self.assertEqual(len(ws_manager.active_connections), initial_count)

    def test_ws_missing_origin_header_with_valid_authentication(self):
        """Legitimate non-browser clients without Origin header connect when authenticated."""
        client = self.get_client()
        login_res = client.post("/api/auth/login", json={
            "email": "operator@disaster.local",
            "password": "operator123",
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        ws_client = self.get_client()
        ws_client.cookies.set("disaster_os_session", token)

        initial_count = len(ws_manager.active_connections)
        # TestClient sends no Origin header by default
        with ws_client.websocket_connect("/ws/simulation") as ws:
            self.assertEqual(len(ws_manager.active_connections), initial_count + 1)
            test_event = {"type": "NON_BROWSER_EVENT", "status": "OK"}
            import asyncio
            asyncio.run(ws_manager.broadcast(test_event))
            msg = ws.receive_json()
            self.assertEqual(msg["type"], "NON_BROWSER_EVENT")

        self.assertEqual(len(ws_manager.active_connections), initial_count)

    def test_ws_unauthenticated_connection_from_trusted_origin_rejected(self):
        """Trusted origin alone is insufficient: unauthenticated handshake must be rejected."""
        client = self.get_client()
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with client.websocket_connect(
                "/ws/simulation",
                headers={"Origin": "http://localhost:3000"},
            ) as ws:
                pass
        self.assertEqual(ctx.exception.code, 1008)
        self.assertEqual(len(ws_manager.active_connections), 0)

    def test_ws_missing_origin_policy_disabled_rejected(self):
        """When DISASTER_OS_ALLOW_MISSING_ORIGIN is disabled, missing Origin header is rejected."""
        import app as app_module
        original_policy = app_module.ALLOW_MISSING_ORIGIN
        try:
            app_module.ALLOW_MISSING_ORIGIN = False

            client = self.get_client()
            login_res = client.post("/api/auth/login", json={
                "email": "operator@disaster.local",
                "password": "operator123",
            })
            token = login_res.json()["token"]

            ws_client = self.get_client()
            ws_client.cookies.set("disaster_os_session", token)

            with self.assertRaises(WebSocketDisconnect) as ctx:
                with ws_client.websocket_connect("/ws/simulation") as ws:
                    pass
            self.assertEqual(ctx.exception.code, 1008)
        finally:
            app_module.ALLOW_MISSING_ORIGIN = original_policy


if __name__ == "__main__":
    unittest.main()
