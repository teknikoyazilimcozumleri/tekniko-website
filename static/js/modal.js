/**
 * Shared modal: open/close, backdrop, Escape, body scroll lock
 * data-modal-open="modal-id"  -> opens the modal
 * data-modal-close            -> closes the modal (button or backdrop)
 */

(function () {
  'use strict';

  function openModal(id) {
    var el = document.getElementById(id);
    if (!el || !el.classList.contains('modal')) return;
    el.classList.add('modal--open');
    el.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    document.addEventListener('keydown', handleEscape);
    // Focus first focusable element (accessibility)
    var focusable = el.querySelector('button, [href], input, select, textarea');
    if (focusable) setTimeout(function () { focusable.focus(); }, 50);
  }

  function closeModal(id) {
    var el = document.getElementById(id);
    if (!el || !el.classList.contains('modal')) return;
    el.classList.remove('modal--open');
    el.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    document.removeEventListener('keydown', handleEscape);
  }

  function handleEscape(e) {
    if (e.key !== 'Escape') return;
    var openModalEl = document.querySelector('.modal.modal--open');
    if (openModalEl) closeModal(openModalEl.id);
  }

  function init() {
    // Open: [data-modal-open="id"]
    document.querySelectorAll('[data-modal-open]').forEach(function (trigger) {
      trigger.addEventListener('click', function (e) {
        e.preventDefault();
        var id = this.getAttribute('data-modal-open');
        if (id) openModal(id);
      });
    });

    // Close: when .modal__backdrop is clicked
    document.querySelectorAll('.modal__backdrop').forEach(function (backdrop) {
      backdrop.addEventListener('click', function () {
        var modal = this.closest('.modal');
        if (modal) closeModal(modal.id);
      });
    });

    // Close: [data-modal-close] — if value set, close that id; else close the containing modal
    document.querySelectorAll('[data-modal-close]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var targetId = this.getAttribute('data-modal-close');
        var modal = this.closest('.modal');
        if (targetId) closeModal(targetId);
        else if (modal) closeModal(modal.id);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Optional: global access
  window.Modal = { open: openModal, close: closeModal };
})();
