// Inkloom AI - Frontend Application Logic

// Application State
const state = {
  users: [],
  currentUser: null,
  currentNavTab: 'creator',
  currentSubTab: 'findings',
  currentGuidelineSubTab: 'rules',
  drafts: [],
  selectedDraftId: null,
  selectedDraftData: null,
  activeFindingTargetId: null,
  editingFindingId: null,
  reviewerTargetDraftId: null,
  tourStep: 1,
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
  await loadUsers();
  await loadDrafts();
  // Auto select first demo draft if available
  if (state.drafts.length > 0) {
    selectDraft(state.drafts[0].id);
  }
});

// --- API HELPER ---
async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (state.currentUser) {
    headers['X-User-Id'] = state.currentUser.id.toString();
  }
  headers['Content-Type'] = 'application/json';

  const response = await fetch(endpoint, {
    ...options,
    headers
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'API Error' }));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// --- USER & AUTH ---
async function loadUsers() {
  try {
    state.users = await apiFetch('/api/users');
    const savedRole = localStorage.getItem('inkloom_active_role') || 'CREATOR';
    const initialUser = state.users.find(u => u.role === savedRole) || state.users[0];
    setCurrentUser(initialUser);
  } catch (err) {
    console.error('Failed to load demo users:', err);
  }
}

function setCurrentUser(user) {
  if (!user) return;
  state.currentUser = user;
  localStorage.setItem('inkloom_active_role', user.role);

  // Update UI Elements
  document.getElementById('active-user-name').innerText = user.name;
  document.getElementById('active-user-role').innerText = user.role;
  document.getElementById('active-avatar').innerText = user.name.charAt(0);
  document.getElementById('active-avatar').style.backgroundColor = user.avatar_color || '#4F46E5';

  // Update Switcher Buttons
  document.querySelectorAll('.role-switch-btn').forEach(btn => {
    btn.classList.remove('active');
  });

  if (user.role === 'CREATOR') {
    document.getElementById('btn-login-creator')?.classList.add('active');
  } else if (user.role === 'REVIEWER') {
    document.getElementById('btn-login-reviewer')?.classList.add('active');
  } else if (user.role === 'ADMIN') {
    document.getElementById('btn-login-admin')?.classList.add('active');
  }
}

function switchDemoUser(role) {
  const user = state.users.find(u => u.role === role);
  if (user) {
    setCurrentUser(user);
    if (role === 'REVIEWER') {
      switchNavTab('reviewer');
    } else if (role === 'ADMIN') {
      switchNavTab('guidelines');
    } else {
      switchNavTab('creator');
    }
  }
}

// --- NAVIGATION & TABS ---
function switchNavTab(tabName) {
  state.currentNavTab = tabName;

  // Toggle active class on nav buttons
  ['creator', 'reviewer', 'guidelines', 'analytics'].forEach(tab => {
    const btn = document.getElementById(`tab-nav-${tab}`);
    const view = document.getElementById(`view-${tab}`);
    if (btn) btn.classList.toggle('active', tab === tabName);
    if (view) view.style.display = tab === tabName ? (tab === 'creator' ? 'grid' : 'block') : 'none';
  });

  if (tabName === 'reviewer') {
    loadReviewerQueue();
  } else if (tabName === 'guidelines') {
    loadGuidelinesData();
  } else if (tabName === 'analytics') {
    loadAnalyticsData();
  } else if (tabName === 'creator') {
    loadDrafts();
  }
}

function switchSubTab(subTabName) {
  state.currentSubTab = subTabName;
  ['findings', 'history', 'audit'].forEach(t => {
    const btn = document.getElementById(`subtab-${t}`);
    const subview = document.getElementById(`subview-${t}`);
    if (btn) btn.classList.toggle('active', t === subTabName);
    if (subview) subview.style.display = t === subTabName ? (t === 'findings' ? 'grid' : 'block') : 'none';
  });
}

function switchGuidelineSubTab(subTab) {
  state.currentGuidelineSubTab = subTab;
  const isRules = subTab === 'rules';
  document.getElementById('guideline-tab-rules')?.classList.toggle('active', isRules);
  document.getElementById('guideline-tab-facts')?.classList.toggle('active', !isRules);
  document.getElementById('guideline-subview-rules').style.display = isRules ? 'block' : 'none';
  document.getElementById('guideline-subview-facts').style.display = !isRules ? 'block' : 'none';
}

// --- DRAFTS & WORKSPACE ---
async function loadDrafts(filterStatus = null) {
  try {
    const url = filterStatus && filterStatus !== 'ALL' ? `/api/drafts?status=${filterStatus}` : '/api/drafts';
    state.drafts = await apiFetch(url);
    renderDraftsSidebar(state.drafts);

    // Update queue count badge
    const inReviewCount = state.drafts.filter(d => d.status === 'IN_REVIEW').length;
    document.getElementById('nav-queue-count').innerText = inReviewCount;
  } catch (err) {
    console.error('Failed to load drafts:', err);
  }
}

function renderDraftsSidebar(drafts) {
  const container = document.getElementById('drafts-sidebar-list');
  if (!drafts || drafts.length === 0) {
    container.innerHTML = '<div style="padding:1.5rem; text-align:center; color:var(--text-sub);">No drafts found</div>';
    return;
  }

  container.innerHTML = drafts.map(d => {
    const isSelected = d.id === state.selectedDraftId;
    const scoreColorClass = d.compliance_score >= 80 ? 'score-high' : d.compliance_score >= 50 ? 'score-mid' : 'score-low';
    const statusClass = `badge-${d.status.toLowerCase()}`;

    return `
      <div class="draft-item-card ${isSelected ? 'selected' : ''}" onclick="selectDraft(${d.id})" id="draft-sidebar-card-${d.id}">
        <div class="draft-card-header">
          <span class="draft-title-text" title="${escapeHtml(d.title)}">${escapeHtml(d.title)}</span>
          <span class="badge-status ${statusClass}">${d.status.replace('_', ' ')}</span>
        </div>
        <div class="draft-card-body">${escapeHtml(d.preview_snippet || 'No text content.')}</div>
        <div class="draft-card-footer">
          <span>v${d.current_version_num} • ${d.pending_findings_count} issues</span>
          <span class="score-pill ${scoreColorClass}">${Math.round(d.compliance_score)}%</span>
        </div>
      </div>
    `;
  }).join('');
}

function filterDrafts(status, btnElement) {
  if (btnElement) {
    btnElement.parentElement.querySelectorAll('.role-switch-btn').forEach(b => b.classList.remove('active'));
    btnElement.classList.add('active');
  }
  loadDrafts(status);
}

async function selectDraft(draftId) {
  state.selectedDraftId = draftId;

  // Highlight card in sidebar
  document.querySelectorAll('.draft-item-card').forEach(el => el.classList.remove('selected'));
  document.getElementById(`draft-sidebar-card-${draftId}`)?.classList.add('selected');

  try {
    const draft = await apiFetch(`/api/drafts/${draftId}`);
    state.selectedDraftData = draft;
    renderDraftView(draft);
  } catch (err) {
    console.error('Failed to fetch draft details:', err);
  }
}

function renderDraftView(draft) {
  // Title & Top Bar
  document.getElementById('selected-draft-title').innerText = draft.title;
  document.getElementById('selected-draft-status').className = `badge-status badge-${draft.status.toLowerCase()}`;
  document.getElementById('selected-draft-status').innerText = draft.status.replace('_', ' ');
  document.getElementById('selected-draft-version').innerText = `v${draft.current_version_num}`;
  document.getElementById('selected-draft-author').innerText = `Author: ${draft.creator ? draft.creator.name : 'Unknown'}`;

  // Meter & Compliance Score
  const score = Math.round(draft.compliance_score);
  const scoreEl = document.getElementById('compliance-score-val');
  const barEl = document.getElementById('compliance-progress-bar');
  const statusLabelEl = document.getElementById('compliance-status-text');

  scoreEl.innerText = `${score}%`;
  barEl.style.width = `${score}%`;

  if (score >= 85) {
    scoreEl.className = 'score-numeric score-high';
    barEl.style.backgroundColor = 'var(--success)';
    statusLabelEl.innerText = 'High Brand Compliance (Ready for Publishing)';
  } else if (score >= 60) {
    scoreEl.className = 'score-numeric score-mid';
    barEl.style.backgroundColor = 'var(--warning)';
    statusLabelEl.innerText = 'Moderate Risk (Substantiation / Term Edits Advised)';
  } else {
    scoreEl.className = 'score-numeric score-low';
    barEl.style.backgroundColor = 'var(--danger)';
    statusLabelEl.innerText = 'High Brand Risk (Actionable Violations Identified)';
  }

  // Badges counts
  document.getElementById('findings-count-badge').innerText = draft.findings.length;
  document.getElementById('versions-count-badge').innerText = draft.versions.length;
  document.getElementById('audit-count-badge').innerText = draft.audit_logs.length;

  // 1. Render Annotated Content (Highlights)
  renderAnnotatedDraft(draft.current_content, draft.findings);

  // 2. Render Findings Cards List
  renderFindingsList(draft.findings);

  // 3. Render Version History
  renderVersionsTimeline(draft.versions);

  // 4. Render Audit Trail
  renderAuditTable(draft.audit_logs);
}

// Highlight matched text in draft content
function renderAnnotatedDraft(content, findings) {
  const container = document.getElementById('annotated-draft-content');
  if (!content) {
    container.innerHTML = '<span style="color:var(--text-sub);">Empty draft. Click "Edit Copy" to paste content.</span>';
    return;
  }

  if (!findings || findings.length === 0) {
    container.innerText = content;
    return;
  }

  // Sort findings by position if available
  const sortedFindings = [...findings].filter(f => f.action_taken === 'pending');
  if (sortedFindings.length === 0) {
    container.innerText = content;
    return;
  }

  // Build markup with highlights
  let markedHtml = escapeHtml(content);
  // Replace matched text occurrences with styled highlight span tags
  sortedFindings.forEach((f, idx) => {
    const rawMatch = f.matched_text;
    const escapedMatch = escapeHtml(rawMatch);
    const sevClass = `sev-${f.severity}`;
    const spanTag = `<span class="flag-highlight ${sevClass}" id="highlight-f-${f.id}" onclick="focusFindingCard(${f.id})" title="${escapeHtml(f.explanation)}">${escapedMatch}</span>`;

    // Safe replace first occurrence
    markedHtml = markedHtml.replace(escapedMatch, spanTag);
  });

  container.innerHTML = markedHtml;
}

function renderFindingsList(findings) {
  const container = document.getElementById('findings-list-container');
  const pendingFindings = (findings || []).filter(f => f.action_taken === 'pending');
  document.getElementById('findings-summary-pill').innerText = `${pendingFindings.length} pending`;

  if (pendingFindings.length === 0) {
    container.innerHTML = `
      <div class="empty-findings-box">
        <div class="empty-icon">✓</div>
        <div style="font-weight:700; color:#fff; margin-bottom:0.25rem;">Clean Brand Compliance</div>
        <div style="font-size:0.8rem;">No active governance issues detected for this draft version.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = pendingFindings.map(f => {
    const sevClass = `sev-${f.severity}`;
    const isVerification = f.status === 'needs verification';
    const statusClass = isVerification ? 'status-verification' : 'status-violation';
    const statusText = isVerification ? 'Needs Verification' : 'Violation';

    return `
      <div class="finding-card ${sevClass}" id="finding-card-${f.id}">
        <div class="finding-header">
          <div class="finding-meta">
            <span class="sev-badge ${sevClass}">${f.severity}</span>
            <span class="status-badge ${statusClass}">${statusText}</span>
          </div>
          <span class="rule-source-tag">${escapeHtml(f.rule_source)}</span>
        </div>

        <!-- Diff side-by-side box -->
        <div class="diff-box">
          <div>
            <div class="diff-label">Flagged Text</div>
            <div class="diff-col-orig">"${escapeHtml(f.matched_text)}"</div>
          </div>
          <div>
            <div class="diff-label">Suggested Rewrite</div>
            <div class="diff-col-suggest">"${escapeHtml(f.suggested_rewrite)}"</div>
          </div>
        </div>

        <div class="finding-explanation">${escapeHtml(f.explanation)}</div>

        <div class="finding-actions">
          <button class="btn-ignore-fix" onclick="ignoreFinding(${f.id})">Ignore</button>
          <button class="btn-edit-fix" onclick="openCustomEditFindingModal(${f.id}, '${escapeQuote(f.matched_text)}')">Edit</button>
          <button class="btn-accept-fix" onclick="acceptFindingFix(${f.id})">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            Accept Fix
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function focusFindingCard(findingId) {
  document.querySelectorAll('.finding-card').forEach(c => c.classList.remove('active-target'));
  document.querySelectorAll('.flag-highlight').forEach(h => h.classList.remove('active-focus'));

  const card = document.getElementById(`finding-card-${findingId}`);
  const highlight = document.getElementById(`highlight-f-${findingId}`);

  if (card) {
    card.classList.add('active-target');
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  if (highlight) {
    highlight.classList.add('active-focus');
  }
}

// --- VERSION HISTORY & AUDIT TIMELINE ---
function renderVersionsTimeline(versions) {
  const container = document.getElementById('versions-timeline-container');
  if (!versions || versions.length === 0) {
    container.innerHTML = '<div style="color:var(--text-sub); padding:1rem;">No versions recorded.</div>';
    return;
  }

  // Reverse sort (newest version first)
  const sorted = [...versions].reverse();
  container.innerHTML = sorted.map(v => {
    return `
      <div class="timeline-item">
        <div class="timeline-meta">
          <span style="font-weight:700; color:#fff;">Version ${v.version_num}</span>
          <span>By ${escapeHtml(v.created_by)} • ${new Date(v.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        <div style="font-size:0.8rem; color:#A5B4FC; font-weight:500;">
          ${escapeHtml(v.change_summary || 'Copy update')}
        </div>
        <div class="timeline-content-preview">${escapeHtml(v.content)}</div>
      </div>
    `;
  }).join('');
}

function renderAuditTable(logs) {
  const tbody = document.getElementById('audit-table-body');
  if (!logs || logs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No audit records.</td></tr>';
    return;
  }

  tbody.innerHTML = logs.map(l => {
    return `
      <tr>
        <td style="white-space:nowrap; font-family:var(--font-mono); font-size:0.75rem;">${new Date(l.timestamp).toLocaleString()}</td>
        <td style="font-weight:600; color:#fff;">${escapeHtml(l.user)}</td>
        <td><span class="badge-status badge-draft">${escapeHtml(l.action)}</span></td>
        <td>${escapeHtml(l.details)}</td>
      </tr>
    `;
  }).join('');
}

// --- FINDINGS ACTIONS ---
async function acceptFindingFix(findingId) {
  if (!state.selectedDraftId) return;
  try {
    const res = await apiFetch(`/api/drafts/${state.selectedDraftId}/findings/${findingId}/accept`, {
      method: 'POST'
    });
    // Reload draft details
    await selectDraft(state.selectedDraftId);
    await loadDrafts();

    // Advance tour step 3 if active
    if (state.tourStep === 3) {
      advanceTourStep(4);
    }
  } catch (err) {
    alert(`Failed to accept fix: ${err.message}`);
  }
}

async function ignoreFinding(findingId) {
  if (!state.selectedDraftId) return;
  try {
    await apiFetch(`/api/drafts/${state.selectedDraftId}/findings/${findingId}/ignore`, {
      method: 'POST'
    });
    await selectDraft(state.selectedDraftId);
    await loadDrafts();
  } catch (err) {
    alert(`Failed to ignore finding: ${err.message}`);
  }
}

function openCustomEditFindingModal(findingId, originalText) {
  state.editingFindingId = findingId;
  document.getElementById('edit-finding-orig').innerText = `"${originalText}"`;
  document.getElementById('custom-finding-input').value = originalText;
  openModal('modal-custom-edit-finding');
}

async function confirmCustomFindingEdit() {
  if (!state.selectedDraftId || !state.editingFindingId) return;
  const customText = document.getElementById('custom-finding-input').value.trim();
  if (!customText) return;

  try {
    await apiFetch(`/api/drafts/${state.selectedDraftId}/findings/${state.editingFindingId}/edit`, {
      method: 'POST',
      body: JSON.stringify({ custom_text: customText })
    });
    closeModal('modal-custom-edit-finding');
    await selectDraft(state.selectedDraftId);
    await loadDrafts();
  } catch (err) {
    alert(`Failed to apply custom edit: ${err.message}`);
  }
}

async function rerunReviewOnCurrentDraft() {
  if (!state.selectedDraftId) return;
  try {
    const btn = document.getElementById('btn-run-review');
    btn.innerHTML = 'Reviewing...';
    await apiFetch(`/api/drafts/${state.selectedDraftId}/review`, { method: 'POST' });
    btn.innerHTML = `<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Review Copy`;
    await selectDraft(state.selectedDraftId);
    await loadDrafts();

    if (state.tourStep === 2) {
      advanceTourStep(3);
    }
  } catch (err) {
    alert(`Review failed: ${err.message}`);
  }
}

// --- DRAFT CREATION & MANUAL EDIT ---
function openNewDraftModal() {
  document.getElementById('new-draft-title').value = '';
  document.getElementById('new-draft-content').value = '';
  openModal('modal-new-draft');
}

async function submitNewDraft() {
  const title = document.getElementById('new-draft-title').value.trim();
  const content = document.getElementById('new-draft-content').value;

  try {
    const res = await apiFetch('/api/drafts', {
      method: 'POST',
      body: JSON.stringify({ title, content })
    });
    closeModal('modal-new-draft');
    await loadDrafts();
    if (res.id) {
      selectDraft(res.id);
    }
  } catch (err) {
    alert(`Failed to create draft: ${err.message}`);
  }
}

function openManualEditModal() {
  if (!state.selectedDraftData) return;
  document.getElementById('edit-draft-content').value = state.selectedDraftData.current_content;
  document.getElementById('edit-draft-summary').value = '';
  openModal('modal-edit-copy');
}

async function saveManualCopyEdit() {
  if (!state.selectedDraftId) return;
  const content = document.getElementById('edit-draft-content').value;
  const summary = document.getElementById('edit-draft-summary').value.trim() || 'Manual copy tweak';

  try {
    await apiFetch(`/api/drafts/${state.selectedDraftId}/update-text`, {
      method: 'POST',
      body: JSON.stringify({ content, change_summary: summary })
    });
    closeModal('modal-edit-copy');
    await selectDraft(state.selectedDraftId);
    await loadDrafts();
  } catch (err) {
    alert(`Failed to save manual edit: ${err.message}`);
  }
}

// --- SUBMIT FOR REVIEW ---
function openSubmitModal() {
  if (!state.selectedDraftId) return;
  document.getElementById('submit-note').value = '';
  openModal('modal-submit-review');
}

async function confirmSubmitForReview() {
  if (!state.selectedDraftId) return;
  const comment = document.getElementById('submit-note').value.trim();

  try {
    await apiFetch(`/api/drafts/${state.selectedDraftId}/submit`, {
      method: 'POST',
      body: JSON.stringify({ comment })
    });
    closeModal('modal-submit-review');
    await selectDraft(state.selectedDraftId);
    await loadDrafts();

    if (state.tourStep === 4) {
      advanceTourStep(5);
    }
  } catch (err) {
    alert(`Submission failed: ${err.message}`);
  }
}

// --- REVIEWER QUEUE ---
async function loadReviewerQueue(filter = 'ALL') {
  try {
    const drafts = await apiFetch('/api/drafts');
    renderReviewerTable(drafts, filter);
  } catch (err) {
    console.error('Failed to load reviewer queue:', err);
  }
}

function renderReviewerTable(drafts, filter = 'ALL') {
  const tbody = document.getElementById('reviewer-queue-tbody');
  let filtered = drafts;
  if (filter !== 'ALL') {
    filtered = drafts.filter(d => d.status === filter);
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:2rem; color:var(--text-sub);">No submissions matching filter.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(d => {
    const scoreColorClass = d.compliance_score >= 80 ? 'score-high' : d.compliance_score >= 50 ? 'score-mid' : 'score-low';
    const statusClass = `badge-${d.status.toLowerCase()}`;

    return `
      <tr>
        <td style="font-weight:600; color:#fff;">${escapeHtml(d.title)}</td>
        <td>${escapeHtml(d.creator ? d.creator.name : 'Unknown')}</td>
        <td><span class="version-pill">v${d.current_version_num}</span></td>
        <td><span class="score-pill ${scoreColorClass}">${Math.round(d.compliance_score)}%</span></td>
        <td><span class="badge-status ${statusClass}">${d.status.replace('_', ' ')}</span></td>
        <td style="font-size:0.75rem; color:var(--text-sub);">${new Date(d.updated_at).toLocaleDateString()}</td>
        <td>
          <button class="btn-primary-sm" onclick="openReviewerDecisionModal(${d.id})">Review & Sign Off</button>
        </td>
      </tr>
    `;
  }).join('');
}

function filterReviewQueue(status, btnElement) {
  if (btnElement) {
    btnElement.parentElement.querySelectorAll('.role-switch-btn').forEach(b => b.classList.remove('active'));
    btnElement.classList.add('active');
  }
  loadReviewerQueue(status);
}

async function openReviewerDecisionModal(draftId) {
  state.reviewerTargetDraftId = draftId;
  try {
    const draft = await apiFetch(`/api/drafts/${draftId}`);
    document.getElementById('reviewer-modal-title').innerText = `Review Draft: ${draft.title} (v${draft.current_version_num})`;
    document.getElementById('reviewer-modal-content').innerText = draft.current_content;
    document.getElementById('reviewer-comment').value = '';
    openModal('modal-reviewer-decision');
  } catch (err) {
    alert(`Failed to load draft for review: ${err.message}`);
  }
}

async function executeReviewerAction(action) {
  if (!state.reviewerTargetDraftId) return;
  const comment = document.getElementById('reviewer-comment').value.trim();

  try {
    await apiFetch(`/api/drafts/${state.reviewerTargetDraftId}/review-action`, {
      method: 'POST',
      body: JSON.stringify({ action, comment })
    });
    closeModal('modal-reviewer-decision');
    await loadReviewerQueue();
    await loadDrafts();

    if (state.tourStep === 5 && action === 'APPROVE') {
      advanceTourStep(6);
    }
  } catch (err) {
    alert(`Review decision failed: ${err.message}`);
  }
}

// --- GUIDELINES & FACTS (ADMIN) ---
async function loadGuidelinesData() {
  try {
    const [rules, facts] = await Promise.all([
      apiFetch('/api/guidelines/rules'),
      apiFetch('/api/guidelines/facts')
    ]);

    document.getElementById('rules-count-badge').innerText = rules.length;
    document.getElementById('facts-count-badge').innerText = facts.length;

    renderBrandRules(rules);
    renderApprovedFacts(facts);
  } catch (err) {
    console.error('Failed to load guidelines:', err);
  }
}

function renderBrandRules(rules) {
  const container = document.getElementById('brand-rules-list');
  if (!rules || rules.length === 0) {
    container.innerHTML = '<div style="color:var(--text-sub);">No rules configured.</div>';
    return;
  }

  container.innerHTML = rules.map(r => {
    const sevClass = `sev-${r.severity}`;
    return `
      <div class="guideline-card-item">
        <div style="display:flex; align-items:center; justify-content:space-between;">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <strong style="color:#fff;">${escapeHtml(r.name)}</strong>
            <span class="sev-badge ${sevClass}">${r.severity}</span>
            <span class="badge-status badge-draft" style="font-size:0.65rem;">${r.rule_type}</span>
          </div>
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span style="font-size:0.75rem; color:var(--text-sub);">${r.version}</span>
            <button class="role-switch-btn ${r.is_active ? 'active' : ''}" style="font-size:0.7rem;" onclick="toggleRuleActive(${r.id})">
              ${r.is_active ? 'Active' : 'Inactive'}
            </button>
          </div>
        </div>
        <div style="font-size:0.8rem; color:#CBD5E1;">${escapeHtml(r.explanation)}</div>
        <div style="display:flex; gap:1rem; font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">
          <span>Pattern: <code>${escapeHtml(r.pattern)}</code></span>
          <span>Preferred: <code style="color:#34D399;">${escapeHtml(r.preferred_term || 'N/A')}</code></span>
          <span>Source: ${escapeHtml(r.source_reference)}</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderApprovedFacts(facts) {
  const container = document.getElementById('approved-facts-list');
  if (!facts || facts.length === 0) {
    container.innerHTML = '<div style="color:var(--text-sub);">No approved facts on file.</div>';
    return;
  }

  container.innerHTML = facts.map(f => {
    return `
      <div class="guideline-card-item" style="border-left:4px solid #10B981;">
        <div style="display:flex; align-items:center; justify-content:space-between;">
          <span class="badge-status badge-approved" style="font-size:0.65rem;">${f.claim_type}</span>
          <span style="font-size:0.75rem; color:var(--text-sub);">${f.version}</span>
        </div>
        <div style="font-size:0.9rem; font-weight:600; color:#fff;">"${escapeHtml(f.fact_text)}"</div>
        <div style="font-size:0.78rem; color:var(--text-muted);">
          <strong>Approved Source:</strong> ${escapeHtml(f.source_reference)}
        </div>
        <div style="font-size:0.75rem; color:var(--text-sub); font-family:var(--font-mono);">
          Keywords: ${escapeHtml(f.keywords)}
        </div>
      </div>
    `;
  }).join('');
}

async function toggleRuleActive(ruleId) {
  try {
    await apiFetch(`/api/guidelines/rules/${ruleId}/toggle`, { method: 'POST' });
    await loadGuidelinesData();
  } catch (err) {
    alert(`Failed to toggle rule: ${err.message}`);
  }
}

function openAddRuleModal() {
  document.getElementById('rule-name-input').value = '';
  document.getElementById('rule-pattern-input').value = '';
  document.getElementById('rule-preferred-input').value = '';
  document.getElementById('rule-explanation-input').value = '';
  document.getElementById('rule-source-input').value = '';
  openModal('modal-add-rule');
}

async function submitAddBrandRule() {
  const payload = {
    name: document.getElementById('rule-name-input').value.trim(),
    rule_type: document.getElementById('rule-type-select').value,
    severity: document.getElementById('rule-severity-select').value,
    pattern: document.getElementById('rule-pattern-input').value.trim(),
    preferred_term: document.getElementById('rule-preferred-input').value.trim(),
    explanation: document.getElementById('rule-explanation-input').value.trim(),
    source_reference: document.getElementById('rule-source-input').value.trim() || 'Brand Governance Manual',
    version: 'v1.0'
  };

  if (!payload.name || !payload.pattern || !payload.explanation) {
    alert('Please complete all required fields.');
    return;
  }

  try {
    await apiFetch('/api/guidelines/rules', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    closeModal('modal-add-rule');
    await loadGuidelinesData();
  } catch (err) {
    alert(`Failed to add brand rule: ${err.message}`);
  }
}

function openAddFactModal() {
  document.getElementById('fact-text-input').value = '';
  document.getElementById('fact-keywords-input').value = '';
  document.getElementById('fact-source-input').value = '';
  openModal('modal-add-fact');
}

async function submitAddApprovedFact() {
  const payload = {
    fact_text: document.getElementById('fact-text-input').value.trim(),
    claim_type: document.getElementById('fact-type-select').value,
    keywords: document.getElementById('fact-keywords-input').value.trim(),
    source_reference: document.getElementById('fact-source-input').value.trim(),
    version: 'v1.0'
  };

  if (!payload.fact_text || !payload.keywords || !payload.source_reference) {
    alert('Please fill out fact text, keywords, and source reference.');
    return;
  }

  try {
    await apiFetch('/api/guidelines/facts', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    closeModal('modal-add-fact');
    await loadGuidelinesData();
  } catch (err) {
    alert(`Failed to add approved fact: ${err.message}`);
  }
}

// --- ANALYTICS DASHBOARD ---
async function loadAnalyticsData() {
  try {
    const data = await apiFetch('/api/analytics');

    // KPIs
    document.getElementById('kpi-total-drafts').innerText = data.total_drafts;
    document.getElementById('kpi-avg-score').innerText = `${data.avg_compliance_score}%`;
    document.getElementById('kpi-approved-drafts').innerText = data.approved_drafts;

    const fixRate = data.total_findings > 0 ? Math.round((data.accepted_fixes / data.total_findings) * 100) : 0;
    document.getElementById('kpi-fix-rate').innerText = `${fixRate}%`;
    document.getElementById('kpi-sub-fixes').innerText = `${data.accepted_fixes} accepted / ${data.total_findings} total findings`;

    // Issue type bars
    const maxIssue = Math.max(...data.issue_types.map(i => i.count), 1);
    const barsContainer = document.getElementById('issue-types-bars');
    barsContainer.innerHTML = data.issue_types.map(item => {
      const pct = Math.round((item.count / maxIssue) * 100);
      return `
        <div>
          <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:0.25rem;">
            <span style="font-weight:600; color:#fff;">${escapeHtml(item.name)}</span>
            <span style="color:var(--text-muted); font-family:var(--font-mono);">${item.count} occurrences</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width:${pct}%; background:#6366F1;"></div>
          </div>
        </div>
      `;
    }).join('');

    // Triggered rules table
    const triggeredTbody = document.getElementById('triggered-rules-tbody');
    triggeredTbody.innerHTML = data.most_triggered_rules.map(r => `
      <tr>
        <td style="color:#CBD5E1; font-weight:500;">${escapeHtml(r.rule)}</td>
        <td style="text-align:right; font-weight:700; font-family:var(--font-mono); color:#fff;">${r.count}</td>
      </tr>
    `).join('') || '<tr><td colspan="2">No rules recorded.</td></tr>';

    // Often ignored rules table
    const ignoredTbody = document.getElementById('ignored-rules-tbody');
    if (data.often_ignored_rules.length === 0) {
      ignoredTbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:1.5rem; color:var(--text-sub);">No frequently ignored rules detected yet. Guidelines have high compliance adherence.</td></tr>';
    } else {
      ignoredTbody.innerHTML = data.often_ignored_rules.map(r => `
        <tr>
          <td style="font-weight:600; color:#fff;">${escapeHtml(r.rule)}</td>
          <td style="color:#EF4444; font-weight:700;">${r.ignored_count}</td>
          <td>${r.total_triggered}</td>
          <td><span class="badge-status badge-changes_requested">${r.ignore_rate}%</span></td>
          <td style="font-size:0.75rem; color:#A5B4FC;">Review wording; creators frequently bypass this rule.</td>
        </tr>
      `).join('');
    }

  } catch (err) {
    console.error('Failed to load analytics:', err);
  }
}

// --- "TRY THIS" 6-STEP INTERACTIVE TOUR ---
function executeTourStep(stepNum) {
  state.tourStep = stepNum;

  // Highlight step in guide banner
  document.querySelectorAll('.guide-step-item').forEach((el, idx) => {
    el.classList.toggle('active', idx + 1 === stepNum);
  });

  if (stepNum === 1) {
    // 1) Open Demo Draft 1
    switchNavTab('creator');
    const d1 = state.drafts.find(d => d.title.includes('Draft 1')) || state.drafts[0];
    if (d1) {
      selectDraft(d1.id);
    }
  } else if (stepNum === 2) {
    // 2) Click Review
    switchNavTab('creator');
    rerunReviewOnCurrentDraft();
  } else if (stepNum === 3) {
    // 3) Accept a fix
    switchNavTab('creator');
    switchSubTab('findings');
    const firstAcceptBtn = document.querySelector('.btn-accept-fix');
    if (firstAcceptBtn) {
      firstAcceptBtn.click();
    } else {
      alert('Click "Accept Fix" on any finding card to create a new draft version.');
    }
  } else if (stepNum === 4) {
    // 4) Submit for Review
    switchNavTab('creator');
    openSubmitModal();
  } else if (stepNum === 5) {
    // 5) Switch to Reviewer and approve
    switchDemoUser('REVIEWER');
    switchNavTab('reviewer');
  } else if (stepNum === 6) {
    // 6) See analytics
    switchNavTab('analytics');
  }
}

function advanceTourStep(nextStep) {
  state.tourStep = nextStep;
  document.querySelectorAll('.guide-step-item').forEach((el, idx) => {
    el.classList.toggle('active', idx + 1 === nextStep);
  });
}

// --- MODAL UTILS ---
function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.style.display = 'flex';
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.style.display = 'none';
}

// --- STRING ESCAPING ---
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeQuote(str) {
  if (!str) return '';
  return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
