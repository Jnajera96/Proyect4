type Summary = { balance: string; count: number };
export function renderSummary(container: HTMLElement, summary: Summary) {
  container.replaceChildren();
  const title = document.createElement('h2');
  title.textContent = 'Estado de movimientos';
  const value = document.createElement('output');
  value.textContent = summary.balance;
  value.setAttribute('aria-label', 'Importe disponible');
  const count = document.createElement('p');
  count.textContent = `${summary.count} movimientos registrados`;
  container.append(title, value, count);
}
export function showError(container: HTMLElement, message: string) {
  const alert = document.createElement('div');
  alert.setAttribute('role', 'alert');
  alert.textContent = message;
  container.replaceChildren(alert);
}
