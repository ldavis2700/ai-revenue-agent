'use strict';
(() => {
  const key = 'apex-response-lab-progress-v1';
  const lessons = [...document.querySelectorAll('[data-lesson]')];
  const progress = document.getElementById('progress');
  let storageAvailable = true;
  try {
    const saved = JSON.parse(localStorage.getItem(key) || '[]');
    if (Array.isArray(saved)) lessons.forEach(input => { input.checked = saved.includes(input.dataset.lesson); });
  } catch (_) { storageAvailable = false; }
  function showProgress() {
    progress.textContent = `${lessons.filter(input => input.checked).length} of ${lessons.length} lessons completed${storageAvailable ? '' : ' (this visit only)'}`;
  }
  lessons.forEach(input => input.addEventListener('change', () => {
    try { localStorage.setItem(key, JSON.stringify(lessons.filter(item => item.checked).map(item => item.dataset.lesson))); }
    catch (_) { storageAvailable = false; }
    showProgress();
  }));
  document.getElementById('reset-progress').addEventListener('click', () => {
    lessons.forEach(input => { input.checked = false; });
    try { localStorage.removeItem(key); } catch (_) { storageAvailable = false; }
    showProgress();
  });
  showProgress();
  let toolkit = '';
  const form = document.getElementById('builder');
  const status = document.getElementById('builder-status');
  form.addEventListener('input', () => {
    toolkit = '';
    document.getElementById('drafts').hidden = true;
    status.textContent = 'Build your starter replies with the updated details.';
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    const company = form.elements.business.value.trim().replace(/[\u0000-\u001f\u007f]/g, '').slice(0, 80);
    if (!company) { status.textContent = 'Enter a business name to continue.'; form.elements.business.focus(); return; }
    const allowed = ['standard cleaning', 'deep cleaning', 'move-out cleaning'];
    const service = allowed.includes(form.elements.service.value) ? form.elements.service.value : allowed[0];
    const replies = {
      inquiry: `Thanks for contacting ${company} about ${service}. How many bedrooms and bathrooms are there, what ZIP code is the home in, and when would you prefer the clean? We will review the details before confirming a quote or availability.`,
      followup: `Following up on the ${service} quote you requested from ${company}. Do you have any questions about the scope? If you would like to continue, reply here so we can review the next step.`,
      handoff: `Thank you for explaining what you need. A team member at ${company} needs to review this request before we can confirm details. What is your preferred way for us to reply?`
    };
    Object.entries(replies).forEach(([name, text]) => { document.getElementById(`reply-${name}`).textContent = text; });
    toolkit = `APEX RESPONSE LAB — STARTER WORKSHEET\nBusiness: ${company}\nService: ${service}\n\nDraft templates for human review. Not an automated sending system.\n\nNEW INQUIRY\n${replies.inquiry}\n\nQUOTE FOLLOW-UP (only after a quote was actually requested and supplied)\n${replies.followup}\n\nHUMAN HANDOFF\n${replies.handoff}\n\nBEFORE USING A DRAFT\n[ ] Check business facts, scope, and availability.\n[ ] Confirm the channel is authorized and check current opt-outs.\n[ ] Check for duplicates and any previous response.\n[ ] Escalate complaints, sensitive details, and uncertain facts.\n\nONE-WEEK ACTION PLAN\nInbox owner: __________\nReview times: __________\nHandoff owner: __________\nFollow-up stopping rules: __________\nBaseline dates: __________\nTest dates: __________\nSingle change being tested: __________\n\nRESULTS (keep customer identifiers in your protected business system)\nMetric | Baseline | Test\nInquiries | ____ | ____\nMedian first-response time | ____ | ____\nQuotes sent | ____ | ____\nAccepted bookings | ____ | ____\nOpt-outs or complaints | ____ | ____\nStaff time in minutes | ____ | ____\n\nWhat improved? __________\nWhat got worse? __________\nOther possible causes? __________\nNext action and review date: __________\n\nOriginal educational material by RMC Family Enterprises LLC.\nYou may adapt these templates for your own business. No sales or revenue guarantee.\n`;
    document.getElementById('drafts').hidden = false;
    status.textContent = 'Three drafts are ready. Check them before use.';
  });
  document.getElementById('download').addEventListener('click', () => {
    if (!toolkit) return;
    const url = URL.createObjectURL(new Blob([toolkit], {type:'text/plain;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url; link.download = 'APEX_Response_Lab_Worksheet.txt';
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
})();
