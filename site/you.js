/**
 * you.js — site-wide "you" indicator.
 *
 * Lower-right floating chip that always shows the visitor their handle.
 * Click → /you.html for the full identity card (walks taken, writings,
 * compounds, hearth visits, witness attestations).
 *
 * Hidden on the page itself (you.html) and on operator surfaces
 * (keep.html, steward.html) to avoid clutter.
 *
 * Cheers vibe: every page silently affirms "we know you're here."
 */
(function () {
  'use strict';

  // Skip on pages where the indicator would be redundant or in the way
  const path = location.pathname.toLowerCase();
  if (path === '/you.html' || path === '/keep.html' || path === '/steward.html'
      || path === '/inbox.html' || path === '/dashboard.html'
      || path === '/curate.html') return;

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function getHandle() {
    try {
      return localStorage.getItem('hearth_handle') || '';
    } catch (e) { return ''; }
  }

  function getVisitorId() {
    try {
      return localStorage.getItem('concordance_visitor_id') || '';
    } catch (e) { return ''; }
  }

  onReady(function () {
    const handle = getHandle();
    const vid = getVisitorId();
    if (!vid) return; // not enough identity yet

    // Build the indicator
    const chip = document.createElement('a');
    chip.id = 'you-indicator';
    chip.href = '/you.html';
    chip.title = 'Your identity in the keeping';
    chip.style.cssText = `
      position: fixed;
      bottom: 14px;
      right: 14px;
      z-index: 900;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 14px 7px 10px;
      background: rgba(22,19,32,0.92);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid var(--border-hi, #3a3142);
      border-left: 3px solid var(--accent, #c9a87c);
      border-radius: 18px;
      color: var(--text-dim, #b3aabd);
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      letter-spacing: 0.06em;
      text-decoration: none;
      cursor: pointer;
      transition: border-color 0.15s, color 0.15s, transform 0.15s;
      box-shadow: 0 4px 14px rgba(0,0,0,0.35);
    `;
    chip.innerHTML = `
      <span style="font-size:14px;color:var(--accent,#c9a87c);">●</span>
      <span><span style="color:var(--muted,#6e6878);">you · </span><span style="color:var(--accent-hi,#e3c498);font-family:'Crimson Pro',Georgia,serif;font-size:13.5px;font-style:italic;letter-spacing:0;">${(handle || 'wanderer').replace(/[<>&"]/g, '')}</span></span>
    `;
    chip.addEventListener('mouseenter', () => {
      chip.style.borderColor = 'var(--accent, #c9a87c)';
      chip.style.transform = 'translateY(-2px)';
    });
    chip.addEventListener('mouseleave', () => {
      chip.style.borderColor = 'var(--border-hi, #3a3142)';
      chip.style.transform = 'translateY(0)';
    });

    // Hide on print
    chip.classList.add('a11y-allow-compact');
    const printStyle = document.createElement('style');
    printStyle.textContent = '@media print { #you-indicator { display: none !important; } }';
    document.head.appendChild(printStyle);

    document.body.appendChild(chip);
  });
})();
