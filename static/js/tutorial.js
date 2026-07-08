/**
 * Tutorial Page - Section Switcher & Hash Router
 *
 * Responsibilities:
 *  - Parse window.location.hash to determine active section
 *  - Show/hide the matching <section data-section> and update sidebar active state
 *  - Populate the mobile dropdown menu from the same TOC data (DRY)
 *  - Handle hashchange (browser back/forward) and click on TOC links
 *  - Smooth-scroll to sub-anchor when a toc-link is clicked
 *
 * Conventions:
 *  - Section anchors: #basic, #extension, #network
 *  - Sub-anchors:    #basic-intro, #basic-model, ... (scroll target inside section)
 *  - Default section: basic
 */
(function () {
  'use strict';

  // ---------- Section labels (used for mobile bar + aria) ----------
  var SECTION_LABELS = {
    basic: '基础功能教程',
    extension: '扩展玩法教程',
    network: '配网教程'
  };

  // ---------- Helpers ----------
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function getSections() { return $$('.tutorial-section'); }
  function getTocGroups() { return $$('.toc-group'); }
  function getTocLinks() { return $$('.toc-link'); }

  // Read current section from hash, or fall back to default.
  function currentSectionFromHash() {
    var hash = (window.location.hash || '').replace('#', '').toLowerCase();
    // strip sub-anchor: #basic-intro -> basic
    var root = hash.split('-')[0];
    if (SECTION_LABELS[root]) return root;
    return 'basic';
  }

  // Map hash like "#basic-intro" to "basic"; "#basic" stays "basic".
  function sectionFromHash(hash) {
    var clean = (hash || '').replace('#', '').toLowerCase();
    var root = clean.split('-')[0];
    return SECTION_LABELS[root] ? root : 'basic';
  }

  // ---------- Core: switch section ----------
  function switchSection(sectionName, options) {
    options = options || {};
    var sections = getSections();
    var groups = getTocGroups();

    sections.forEach(function (sec) {
      if (sec.getAttribute('data-section') === sectionName) {
        sec.classList.remove('hidden');
      } else {
        sec.classList.add('hidden');
      }
    });

    groups.forEach(function (g) {
      if (g.getAttribute('data-section') === sectionName) {
        g.classList.add('active');
      } else {
        g.classList.remove('active');
      }
    });

    // Update active state on sub-links (only those belonging to the active section).
    getTocLinks().forEach(function (a) {
      if (a.getAttribute('data-section-link') === sectionName) {
        // No .active by default; sub-link active is only set on scroll/click.
      }
    });

    // Update mobile label & mobile menu active item.
    var mobileLabel = $('#tutorial-mobile-label');
    if (mobileLabel) mobileLabel.textContent = SECTION_LABELS[sectionName] || '';

    $$('#tutorial-mobile-menu a').forEach(function (a) {
      if (a.getAttribute('data-section-link') === sectionName) {
        a.classList.add('active');
      } else {
        a.classList.remove('active');
      }
    });

    // Sync URL hash (only on explicit user navigation, not on initial load).
    if (options.updateHash !== false) {
      var desiredHash = '#' + sectionName;
      if (window.location.hash !== desiredHash) {
        // Use replaceState to avoid spamming history when toggling via group title.
        history.replaceState(null, '', desiredHash);
      }
    }

    // If we switched section, scroll content area to top (skip on initial load).
    if (options.scrollToTop) {
      var content = $('.tutorial-content');
      if (content && typeof content.scrollIntoView === 'function') {
        content.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }

  // ---------- Mobile menu population (DRY: built from sidebar TOC) ----------
  function buildMobileMenu() {
    var menu = $('#tutorial-mobile-menu');
    if (!menu) return;
    menu.innerHTML = '';

    getTocGroups().forEach(function (group) {
      var sectionName = group.getAttribute('data-section');
      var titleEl = group.querySelector('.toc-group-title');
      var titleText = titleEl ? titleEl.textContent.trim() : sectionName;

      var groupTitle = document.createElement('li');
      groupTitle.className = 'mobile-group-title';
      groupTitle.textContent = titleText;
      menu.appendChild(groupTitle);

      $$('.toc-link', group).forEach(function (link) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = link.getAttribute('href');
        a.textContent = link.textContent;
        a.setAttribute('data-section-link', sectionName);
        li.appendChild(a);
        menu.appendChild(li);
      });
    });
  }

  // ---------- Mobile bar toggle ----------
  function bindMobileToggle() {
    var btn = $('#tutorial-mobile-toggle');
    var menu = $('#tutorial-mobile-menu');
    if (!btn || !menu) return;

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      if (expanded) {
        btn.setAttribute('aria-expanded', 'false');
        menu.classList.add('hidden');
      } else {
        btn.setAttribute('aria-expanded', 'true');
        menu.classList.remove('hidden');
      }
    });

    // Click outside to close
    document.addEventListener('click', function (e) {
      if (!btn.contains(e.target) && !menu.contains(e.target)) {
        btn.setAttribute('aria-expanded', 'false');
        menu.classList.add('hidden');
      }
    });

    // Selecting a mobile menu item closes the dropdown
    menu.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        btn.setAttribute('aria-expanded', 'false');
        menu.classList.add('hidden');
      }
    });
  }

  // ---------- Sub-link active highlighting via scroll ----------
  function setupScrollSpy() {
    var contentCards = $$('.content-card[id]');
    if (!contentCards.length) return;

    function updateActiveLink() {
      var scrollTop = window.scrollY || document.documentElement.scrollTop;
      var offset = 120; // top nav + breathing room
      var currentId = null;

      for (var i = 0; i < contentCards.length; i++) {
        var el = contentCards[i];
        // Skip cards inside hidden sections
        if (el.closest('.tutorial-section.hidden')) continue;
        var rect = el.getBoundingClientRect();
        if (rect.top - offset <= 0) {
          currentId = el.id;
        } else {
          break;
        }
      }

      getTocLinks().forEach(function (a) {
        var href = a.getAttribute('href') || '';
        if (href === '#' + currentId) {
          a.classList.add('active');
        } else {
          a.classList.remove('active');
        }
      });
    }

    // Auto-expand parent sub-group if the active sub-link is inside one.
    function expandActiveParentGroup() {
      var active = $$('.toc-link.active')[0];
      if (!active) return;
      var parentGroup = active.closest('.toc-subgroup');
      if (parentGroup && parentGroup.classList.contains('collapsed')) {
        parentGroup.classList.remove('collapsed');
      }
    }

    var ticking = false;
    window.addEventListener('scroll', function () {
      if (!ticking) {
        window.requestAnimationFrame(function () {
          updateActiveLink();
          expandActiveParentGroup();
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // ---------- Click handlers ----------
  function bindClicks() {
    // Sidebar group title -> switch section
    $$('.toc-group-title').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var section = a.getAttribute('data-section-link');
        if (!section) return;
        e.preventDefault();
        switchSection(section, { scrollToTop: true });
      });
    });

    // Sub-group title -> toggle collapse
    $$('.toc-subgroup-title').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var group = btn.closest('.toc-subgroup');
        if (!group) return;
        group.classList.toggle('collapsed');
      });
    });

    // Sub-link click: switch section (if needed) and scroll to anchor.
    getTocLinks().forEach(function (a) {
      a.addEventListener('click', function (e) {
        var section = a.getAttribute('data-section-link');
        var href = a.getAttribute('href') || '';
        if (!section || !href) return;
        e.preventDefault();

        var currentSec = sectionFromHash(window.location.hash);
        if (currentSec !== section) {
          switchSection(section, { updateHash: false });
        }

        var target = document.getElementById(href.replace('#', ''));
        if (target) {
          // Defer scroll until after section is shown
          setTimeout(function () {
            var offset = 80;
            var top = target.getBoundingClientRect().top + window.scrollY - offset;
            window.scrollTo({ top: top, behavior: 'smooth' });
          }, 50);
        }

        // Update URL hash
        history.replaceState(null, '', href);
      });
    });

    // Mobile menu links reuse the same data-section-link + href as sidebar links.
    // To keep things simple, delegate click on the menu container.
    var mobileMenu = $('#tutorial-mobile-menu');
    if (mobileMenu) {
      mobileMenu.addEventListener('click', function (e) {
        if (e.target.tagName !== 'A') return;
        var section = e.target.getAttribute('data-section-link');
        var href = e.target.getAttribute('href') || '';
        if (!section || !href) return;
        e.preventDefault();

        switchSection(section, { updateHash: false });

        var target = document.getElementById(href.replace('#', ''));
        if (target) {
          setTimeout(function () {
            var offset = 80;
            var top = target.getBoundingClientRect().top + window.scrollY - offset;
            window.scrollTo({ top: top, behavior: 'smooth' });
          }, 50);
        }
        history.replaceState(null, '', href);
      });
    }
  }

  // ---------- Hash change (browser back/forward) ----------
  function bindHashChange() {
    window.addEventListener('hashchange', function () {
      var hash = window.location.hash;
      var section = sectionFromHash(hash);
      switchSection(section, { updateHash: false });

      // If hash points to a sub-anchor, scroll to it after section is shown.
      var sub = (hash || '').replace('#', '');
      if (sub && sub !== section) {
        setTimeout(function () {
          var target = document.getElementById(sub);
          if (target) {
            var offset = 80;
            var top = target.getBoundingClientRect().top + window.scrollY - offset;
            window.scrollTo({ top: top, behavior: 'smooth' });
          }
        }, 50);
      }
    });
  }

  // ---------- Init ----------
  function init() {
    buildMobileMenu();
    bindMobileToggle();
    bindClicks();
    bindHashChange();

    // Initial section from hash (do not push new history)
    var initial = currentSectionFromHash();
    switchSection(initial, { updateHash: false });

    setupScrollSpy();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
