const hamburger = document.querySelector('.hamburger');
  const navLinks = document.querySelector('.nav-links');

  if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
      const isOpen = navLinks.classList.toggle('open');
      hamburger.setAttribute('aria-expanded', String(isOpen));
    });
  }

  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const selector = a.getAttribute('href');
      const target = selector && selector.length > 1 ? document.querySelector(selector) : document.body;
      if (target) {
        e.preventDefault();
        const offset = 76;
        const top = target === document.body ? 0 : target.offsetTop - offset;
        window.scrollTo({ top, behavior: 'smooth' });
        if (navLinks) navLinks.classList.remove('open');
        if (hamburger) hamburger.setAttribute('aria-expanded', 'false');
      }
    });
  });

  document.querySelectorAll('a[target="_blank"]').forEach(a => {
    a.rel = 'noopener noreferrer';
  });
