export function createHealthScoreRing(score, size = 120, stroke = 12) {
  const radius = (size - stroke) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;

  let colorClass = 'stroke-passed';
  if (score < 50) colorClass = 'stroke-critical';
  else if (score < 80) colorClass = 'stroke-warning';

  const svg = `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="health-score-ring">
      <circle
        class="ring-bg"
        stroke-width="${stroke}"
        stroke="var(--bg-surface-hover)"
        fill="transparent"
        r="${radius}"
        cx="${size / 2}"
        cy="${size / 2}"
      />
      <circle
        class="ring-progress ${colorClass}"
        stroke-width="${stroke}"
        stroke-dasharray="${circumference} ${circumference}"
        stroke-dashoffset="${offset}"
        stroke-linecap="round"
        fill="transparent"
        r="${radius}"
        cx="${size / 2}"
        cy="${size / 2}"
        style="transform: rotate(-90deg); transform-origin: 50% 50%; transition: stroke-dashoffset 1s ease-in-out;"
      />
      <text
        x="50%"
        y="50%"
        dominant-baseline="central"
        text-anchor="middle"
        font-family="Inter"
        font-weight="700"
        font-size="${size * 0.25}px"
        fill="var(--text-primary)"
      >
        ${score}
      </text>
    </svg>
  `;

  // We add a tiny bit of CSS injected dynamically or assume it's handled.
  // We'll define stroke colors inline for simplicity or use CSS variables.

  const div = document.createElement('div');
  div.innerHTML = svg;
  
  // Apply actual colors to the classes
  const ring = div.querySelector('.ring-progress');
  if (colorClass === 'stroke-passed') ring.style.stroke = 'var(--color-passed)';
  if (colorClass === 'stroke-warning') ring.style.stroke = 'var(--color-warning)';
  if (colorClass === 'stroke-critical') ring.style.stroke = 'var(--color-critical)';

  return div.firstElementChild;
}
