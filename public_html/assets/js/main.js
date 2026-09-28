document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname || '/';
    const links = document.querySelectorAll('.section-left__content a');

    links.forEach(link => {
        const href = link.getAttribute('href');
        // Сравниваем href с текущим путём. Если совпадает — ставим active
        if (path === href) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
});