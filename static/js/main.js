// ============================================
// BestOneGifted - Interaction & Animation JS
// (vanilla JS only, no dependencies, keeps site fast)
// ============================================

function getCookie(name) {
    let value = null;
    if (document.cookie) {
        document.cookie.split(';').forEach(function (c) {
            c = c.trim();
            if (c.startsWith(name + '=')) value = decodeURIComponent(c.slice(name.length + 1));
        });
    }
    return value;
}
const CSRF_TOKEN = getCookie('csrftoken');

document.addEventListener('DOMContentLoaded', function () {

    // ---------- 1) Auto-hide messages ----------
    document.querySelectorAll('.messages .message').forEach(function (msg) {
        setTimeout(function () {
            msg.style.transition = 'opacity 0.5s';
            msg.style.opacity = '0';
            setTimeout(function () { msg.remove(); }, 500);
        }, 4000);
    });

    // ---------- 2) Scroll-reveal ----------
    var revealEls = document.querySelectorAll('.reveal, .reveal-stagger');
    if ('IntersectionObserver' in window && revealEls.length) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('in-view');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
        revealEls.forEach(function (el) { observer.observe(el); });
    } else {
        revealEls.forEach(function (el) { el.classList.add('in-view'); });
    }

    // ---------- 3) Cart Drawer open/close ----------
    var drawer = document.getElementById('cart-drawer');
    var drawerOverlay = document.getElementById('cart-drawer-overlay');
    function openDrawer() { drawer.classList.add('open'); drawerOverlay.classList.add('open'); }
    function closeDrawer() { drawer.classList.remove('open'); drawerOverlay.classList.remove('open'); }

    var cartIconLink = document.getElementById('cart-icon-link');
    var mobileCartLink = document.getElementById('mobile-cart-link');
    if (cartIconLink) cartIconLink.addEventListener('click', function (e) { e.preventDefault(); openDrawer(); });
    if (mobileCartLink) mobileCartLink.addEventListener('click', function (e) { e.preventDefault(); openDrawer(); });
    var drawerClose = document.getElementById('drawer-close');
    if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
    if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

    function updateCartBadges(count) {
        document.querySelectorAll('.cart-link .icon-badge, #mobile-cart-link em').forEach(function (b) { b.remove(); });
        if (count > 0) {
            if (cartIconLink) {
                var b = document.createElement('span');
                b.className = 'icon-badge';
                b.textContent = count;
                cartIconLink.appendChild(b);
            }
            if (mobileCartLink) {
                var em = document.createElement('em');
                em.textContent = count;
                mobileCartLink.appendChild(em);
            }
        }
    }

    // ---------- 3b) Add-to-cart success toast (visual-only, Part 2) ----------
    function showCartToast(text) {
        var toast = document.createElement('div');
        toast.className = 'cart-toast';
        toast.textContent = text;
        document.body.appendChild(toast);
        requestAnimationFrame(function () { toast.classList.add('show'); });
        setTimeout(function () {
            toast.classList.remove('show');
            setTimeout(function () { toast.remove(); }, 300);
        }, 1800);
    }

    // ---------- 4) AJAX Add-to-Cart for all .js-cart-form ----------
    function bindCartForms() {
        document.querySelectorAll('.js-cart-form').forEach(function (form) {
            if (form.dataset.bound) return;
            form.dataset.bound = '1';
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                var formData = new FormData(form);
                // Visual-only loading state on the submit button (Part 2: add-to-cart polish)
                var submitBtn = form.querySelector('button[type=submit]');
                var btnOriginalText = submitBtn ? submitBtn.textContent : null;
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.classList.add('is-loading');
                    submitBtn.textContent = 'Adding...';
                }
                function restoreBtn() {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.classList.remove('is-loading');
                        submitBtn.textContent = btnOriginalText;
                    }
                }
                fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    body: formData,
                }).then(function (res) { return res.json(); })
                  .then(function (data) {
                    if (data.drawer_html) {
                        document.getElementById('drawer-content').innerHTML = data.drawer_html;
                        bindCartForms();
                    }
                    if (typeof data.count !== 'undefined') updateCartBadges(data.count);
                    if (cartIconLink) {
                        cartIconLink.classList.remove('bump');
                        void cartIconLink.offsetWidth;
                        cartIconLink.classList.add('bump');
                    }
                    restoreBtn();
                    showCartToast('Added to cart');
                    openDrawer();
                  }).catch(function () { restoreBtn(); form.submit(); });
            });
        });
    }
    bindCartForms();

    // ---------- 5) Wishlist heart toggle (AJAX) ----------
    document.querySelectorAll('.wishlist-heart').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var productId = btn.dataset.productId;
            fetch('/wishlist/toggle/' + productId + '/', {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': CSRF_TOKEN },
            }).then(function (res) { return res.json(); })
              .then(function (data) {
                btn.classList.toggle('active', data.in_wishlist);
              });
        });
    });

    // ---------- 6) Quick View modal ----------
    var qvOverlay = document.getElementById('quick-view-overlay');
    var qvModal = document.getElementById('quick-view-modal');
    var qvContent = document.getElementById('qv-content');
    function closeQV() { qvModal.classList.remove('open'); qvOverlay.classList.remove('open'); }
    document.querySelectorAll('.quick-view-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var slug = btn.dataset.slug;
            fetch('/product/' + slug + '/quick-view/')
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    qvContent.innerHTML = data.html;
                    qvModal.classList.add('open');
                    qvOverlay.classList.add('open');
                    bindCartForms();
                });
        });
    });
    var qvClose = document.getElementById('qv-close');
    if (qvClose) qvClose.addEventListener('click', closeQV);
    if (qvOverlay) qvOverlay.addEventListener('click', function () { closeQV(); closeDrawer(); });

    // ---------- 7) Search predictive dropdown ----------
    var searchInput = document.getElementById('search-input');
    var searchDropdown = document.getElementById('search-dropdown');
    var searchTimer = null;
    var popularTags = ['Photo Mug', 'Name Plate', 'LED Lamp', 'Couple T-Shirt', 'Keychain'];

    function showPopular() {
        var tagsHtml = popularTags.map(function (t) { return '<span class="sd-tag" data-tag="' + t + '">' + t + '</span>'; }).join('');
        searchDropdown.innerHTML = '<div class="sd-popular">Popular Searches</div><div class="sd-tags">' + tagsHtml + '</div>';
        searchDropdown.classList.add('open');
        searchDropdown.querySelectorAll('.sd-tag').forEach(function (tag) {
            tag.addEventListener('click', function () {
                searchInput.value = tag.dataset.tag;
                searchInput.form.submit();
            });
        });
    }

    if (searchInput) {
        searchInput.addEventListener('focus', function () {
            if (!searchInput.value) showPopular();
        });
        searchInput.addEventListener('input', function () {
            var q = searchInput.value.trim();
            clearTimeout(searchTimer);
            if (!q) { showPopular(); return; }
            searchTimer = setTimeout(function () {
                fetch('/search/suggest/?q=' + encodeURIComponent(q))
                    .then(function (res) { return res.json(); })
                    .then(function (data) {
                        if (!data.results.length) {
                            searchDropdown.innerHTML = '<div class="sd-empty">No products found for "' + q + '"</div>';
                        } else {
                            searchDropdown.innerHTML = data.results.map(function (r) {
                                return '<a class="sd-item" href="' + r.url + '">' +
                                    (r.image ? '<img src="' + r.image + '" alt="">' : '') +
                                    '<span>' + r.name + '<br><strong>Rs. ' + r.price + '</strong></span></a>';
                            }).join('');
                        }
                        searchDropdown.classList.add('open');
                    });
            }, 300);
        });
        document.addEventListener('click', function (e) {
            if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
                searchDropdown.classList.remove('open');
            }
        });
    }

    // ---------- 8) Newsletter AJAX submit ----------
    var newsletterForm = document.getElementById('newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var formData = new FormData(newsletterForm);
            fetch(newsletterForm.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: formData,
            }).then(function (res) { return res.json(); })
              .then(function (data) {
                newsletterForm.innerHTML = '<p style="color:#fff;">' + data.message + '</p>';
              });
        });
    }

    // ---------- 9) Loading progress bar ----------
    var progress = document.createElement('div');
    progress.id = 'page-progress';
    document.body.appendChild(progress);
    window.addEventListener('beforeunload', function () { progress.style.width = '70%'; });

    // ---------- 10) Auto-focus first field on auth forms ----------
    var authForm = document.querySelector('.auth-form');
    if (authForm) {
        var firstInput = authForm.querySelector('input:not([type=hidden])');
        if (firstInput) firstInput.focus();
    }

    // ---------- 11b) Mobile hamburger nav drawer (new — redesign) ----------
    var mobileNavDrawer = document.getElementById('mobile-nav-drawer');
    var mobileNavOverlay = document.getElementById('mobile-nav-overlay');
    var mobileNavOpenBtn = document.getElementById('mobile-nav-open');
    var mobileNavCloseBtn = document.getElementById('mobile-nav-close');
    function openMobileNav() { if (mobileNavDrawer) mobileNavDrawer.classList.add('open'); if (mobileNavOverlay) mobileNavOverlay.classList.add('open'); }
    function closeMobileNav() { if (mobileNavDrawer) mobileNavDrawer.classList.remove('open'); if (mobileNavOverlay) mobileNavOverlay.classList.remove('open'); }
    if (mobileNavOpenBtn) mobileNavOpenBtn.addEventListener('click', openMobileNav);
    if (mobileNavCloseBtn) mobileNavCloseBtn.addEventListener('click', closeMobileNav);
    if (mobileNavOverlay) mobileNavOverlay.addEventListener('click', closeMobileNav);

    // ---------- 11c) Product card mouse-following spotlight (Part 2 — desktop only) ----------
    if (window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
        document.querySelectorAll('.product-card').forEach(function (card) {
            card.addEventListener('mousemove', function (e) {
                var rect = card.getBoundingClientRect();
                var x = ((e.clientX - rect.left) / rect.width) * 100;
                var y = ((e.clientY - rect.top) / rect.height) * 100;
                card.style.setProperty('--spot-x', x + '%');
                card.style.setProperty('--spot-y', y + '%');
            });
        });
    }

    // ---------- 11) Login popup: show once, a few seconds after the user starts scrolling ----------
    var loginPopup = document.getElementById('login-popup');
    var loginPopupOverlay = document.getElementById('login-popup-overlay');
    if (loginPopup && loginPopupOverlay) {
        var popupShown = sessionStorage.getItem('bog_login_popup_shown');
        var scrollTimer = null;
        var hasScrolled = false;

        function openLoginPopup() {
            if (popupShown) return;
            loginPopup.classList.add('open');
            loginPopupOverlay.classList.add('open');
            sessionStorage.setItem('bog_login_popup_shown', '1');
            popupShown = true;
        }
        function closeLoginPopup() {
            loginPopup.classList.remove('open');
            loginPopupOverlay.classList.remove('open');
        }

        window.addEventListener('scroll', function () {
            if (hasScrolled || popupShown) return;
            hasScrolled = true;
            scrollTimer = setTimeout(openLoginPopup, 3000); // 3s after user starts scrolling
        }, { passive: true });

        var closeBtn = document.getElementById('login-popup-close');
        if (closeBtn) closeBtn.addEventListener('click', closeLoginPopup);
        loginPopupOverlay.addEventListener('click', closeLoginPopup);
    }
});