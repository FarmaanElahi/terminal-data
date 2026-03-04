export interface UserPriceAlert {
  id: string;
  price: number;
  operator: string;
  label: string;
  color: string;
}

export interface AlertHit {
  alert: UserPriceAlert;
  distance: number;
}

export function getAlertColor(operator: string): string {
  return operator === "<=" || operator === "<" ? "#EF4444" : "#22C55E";
}

export function normalizeOperator(operator: string): string {
  if (operator === "<") return "<=";
  if (operator === ">") return ">=";
  return operator;
}

export function getPriceFromEvent(
  container: HTMLElement,
  clientY: number,
  coordinateToPrice: (y: number) => number | null,
): number | null {
  const rect = container.getBoundingClientRect();
  const y = clientY - rect.top;
  const price = coordinateToPrice(y);
  return price == null || !Number.isFinite(price) ? null : price;
}

export function findNearestAlertByY(
  alerts: UserPriceAlert[],
  y: number,
  priceToCoordinate: (price: number) => number | null,
  thresholdPx = 8,
): AlertHit | null {
  let best: AlertHit | null = null;

  for (const alert of alerts) {
    const cy = priceToCoordinate(alert.price);
    if (cy == null || !Number.isFinite(cy)) continue;
    const dist = Math.abs(cy - y);
    if (dist > thresholdPx) continue;
    if (!best || dist < best.distance) {
      best = { alert, distance: dist };
    }
  }

  return best;
}
