import React, { memo, useEffect, useState } from 'react';

const AnimatedCounter = memo(function AnimatedCounter({ value, duration = 800, prefix = '', suffix = '' }) {
  const numericVal = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]+/g, ''));
  const isNumeric = !isNaN(numericVal);
  const [count, setCount] = useState(isNumeric ? 0 : value);

  useEffect(() => {
    if (!isNumeric) {
      setCount(value);
      return;
    }

    let start = 0;
    const end = numericVal;
    const startTime = performance.now();

    const updateCounter = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = progress * (2 - progress);
      const current = Math.floor(start + (end - start) * easedProgress);
      setCount(current);

      if (progress < 1) {
        requestAnimationFrame(updateCounter);
      } else {
        setCount(end);
      }
    };

    requestAnimationFrame(updateCounter);
  }, [value, numericVal, isNumeric, duration]);

  if (!isNumeric) {
    return <span>{value}</span>;
  }

  return (
    <span>
      {prefix}
      {count.toLocaleString()}
      {suffix}
    </span>
  );
});

export default AnimatedCounter;
