/* Presentation only: Django still validates every input and claims each debit. */
(() => {
  const card = document.querySelector('[name="card_number"]');
  const expiry = document.querySelector('[name="expiry"]');
  if (card) card.addEventListener('input', () => {
    const digits = card.value.replace(/\D/g, '').slice(0, 16);
    card.value = digits.match(/.{1,4}/g)?.join(' ') || '';
  });
  if (expiry) expiry.addEventListener('input', () => {
    const digits = expiry.value.replace(/\D/g, '').slice(0, 4);
    expiry.value = digits.length > 2 ? digits.slice(0, 2) + '/' + digits.slice(2) : digits;
  });
  const timer = document.querySelector('[data-countdown]');
  if (timer) {
    const deadline = Date.now() + Number(timer.dataset.countdown) * 1000;
    const label = timer.querySelector('span');
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      label.textContent = remaining ? String(Math.floor(remaining / 60)).padStart(2, '0') + ':' + String(remaining % 60).padStart(2, '0') : 'Kod muddati tugadi';
      if (!remaining) clearInterval(interval);
    };
    const interval = setInterval(tick, 1000);
    tick();
  }
  document.querySelector('#payment-form')?.addEventListener('submit', (event) => {
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    button.querySelector('span').textContent = 'Kutilmoqda…';
  });
})();
