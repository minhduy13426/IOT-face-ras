/* ══════════════════════════════════════════════════════════════
   FaceDF — app.js  |  Frontend Logic
   Vanilla JS, no framework, ES2022
══════════════════════════════════════════════════════════════ */

const API = ''; // same origin — FastAPI serves static files at /
let PI_IP = localStorage.getItem('pi-ip') || '192.168.1.10'; // Mặc định, sẽ cho phép người dùng đổi

/* ══════════════════════════════════════════════════════════════
   AUTHENTICATION CHECK (M3)
══════════════════════════════════════════════════════════════ */
function checkAuth() {
  const token = localStorage.getItem('access_token');
  if (!token) {
    window.location.replace('login.html');
    return false;
  }
  const badge = document.getElementById('tenantBadge');
  if (badge) {
    const tenantName = localStorage.getItem('tenant_name') || 'Tổ chức';
    badge.textContent = `🏢 ${tenantName}`;
    badge.title = `Tổ chức: ${tenantName}`;
  }
  return true;
}

function logout() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('tenant_name');
  localStorage.removeItem('tenant_code');
  window.location.replace('login.html');
}

// Chạy kiểm tra đăng nhập ngay khi file được nạp
if (!checkAuth()) {
  throw new Error("Chưa đăng nhập -> Đang chuyển hướng sang login.html");
}

/* ══════════════════════════════════════════════════════════════
   UTILITY
══════════════════════════════════════════════════════════════ */

/** Format ISO timestamp to Vietnamese locale string */
function fmtDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

/** Format "YYYY-MM-DD" to Vietnamese date string */
function fmtDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

/** Today's date as YYYY-MM-DD */
function todayISO() {
  return new Date().toLocaleDateString('en-CA'); // yyyy-mm-dd
}

/** Fetch JSON from API, returns { data, error } */
async function apiFetch(path, opts = {}) {
  try {
    const token = localStorage.getItem('access_token');
    opts.headers = opts.headers || {};
    if (token) {
      if (opts.headers instanceof Headers) {
        opts.headers.set('Authorization', `Bearer ${token}`);
      } else {
        opts.headers['Authorization'] = `Bearer ${token}`;
      }
    }
    const res = await fetch(API + path, opts);
    if (res.status === 401 && !path.includes('/api/auth/login')) {
      // Token hết hạn hoặc không hợp lệ -> xóa token và chuyển trang
      localStorage.removeItem('access_token');
      localStorage.removeItem('tenant_name');
      localStorage.removeItem('tenant_code');
      window.location.replace('login.html');
      return { data: null, error: 'Phiên đăng nhập hết hạn' };
    }
    const json = await res.json().catch(() => ({}));
    if (!res.ok) return { data: null, error: json.detail || `Lỗi ${res.status}` };
    return { data: json, error: null };
  } catch (e) {
    return { data: null, error: e.message };
  }
}

/* ══════════════════════════════════════════════════════════════
   TOAST
══════════════════════════════════════════════════════════════ */
const toastContainer = document.getElementById('toastContainer');

function showToast(type, title, msg = '', duration = 4000) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `
    <span class="toast-icon">${icons[type] || '📢'}</span>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      ${msg ? `<div class="toast-msg">${msg}</div>` : ''}
    </div>`;
  toastContainer.appendChild(el);
  setTimeout(() => {
    el.classList.add('hiding');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, duration);
}

/* ══════════════════════════════════════════════════════════════
   LOADING OVERLAY
══════════════════════════════════════════════════════════════ */
const loadingOverlay = document.getElementById('loadingOverlay');
let _loadingCount = 0;
function showLoading() { _loadingCount++; loadingOverlay.classList.add('active'); }
function hideLoading() { _loadingCount = Math.max(0, _loadingCount - 1); if (!_loadingCount) loadingOverlay.classList.remove('active'); }

/* ══════════════════════════════════════════════════════════════
   CLOCK
══════════════════════════════════════════════════════════════ */
const clockEl = document.getElementById('liveClock');
function updateClock() {
  clockEl.textContent = new Date().toLocaleString('vi-VN', {
    weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}
updateClock();
setInterval(updateClock, 1000);

/* ══════════════════════════════════════════════════════════════
   NAVIGATION
══════════════════════════════════════════════════════════════ */
const tabTitles = { 
  dashboard: 'Dashboard', 
  students: 'Sinh viên', 
  attendance: 'Điểm danh', 
  report: 'Báo cáo',
  reports: 'Báo cáo' 
};
const pageTitleEl = document.getElementById('pageTitle');

function switchTab(name) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.tab === name));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.toggle('active', t.id === `tab-${name}`));
  pageTitleEl.textContent = tabTitles[name] || name;

  if (name === 'dashboard') loadDashboard();
  if (name === 'students') loadStudents();
  if (name === 'attendance') { loadAttendanceForDate(document.getElementById('attendanceDate').value || todayISO()); }
  if (name === 'report' || name === 'reports') { 
    loadReport(document.getElementById('reportDate')?.value || todayISO()); 
    loadShiftSettings();
  }
}

document.querySelectorAll('.nav-item').forEach(n => {
  n.addEventListener('click', e => { e.preventDefault(); switchTab(n.dataset.tab); closeSidebar(); });
});

/* Sidebar mobile toggle */
const sidebar = document.getElementById('sidebar');
const menuBtn = document.getElementById('menuToggle');
const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');

function closeSidebar() { if (window.innerWidth <= 768) sidebar.classList.remove('open'); }
menuBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
document.addEventListener('click', e => { if (!sidebar.contains(e.target) && !menuBtn.contains(e.target)) closeSidebar(); });

// Desktop sidebar collapse
sidebarCollapseBtn.addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
  localStorage.setItem('facedf-sidebar', sidebar.classList.contains('collapsed') ? 'collapsed' : 'expanded');
});

// Init sidebar from storage
if (localStorage.getItem('facedf-sidebar') === 'collapsed') {
  sidebar.classList.add('collapsed');
}

/* Refresh button */
document.getElementById('refreshBtn').addEventListener('click', function () {
  this.classList.add('spinning');
  const active = document.querySelector('.tab-content.active')?.id;
  const tabName = active?.replace('tab-', '');
  if (tabName === 'dashboard') loadDashboard().finally(() => this.classList.remove('spinning'));
  else if (tabName === 'students') loadStudents().finally(() => this.classList.remove('spinning'));
  else if (tabName === 'attendance') {
    loadAttendanceForDate(document.getElementById('attendanceDate').value || todayISO())
      .finally(() => this.classList.remove('spinning'));
  } else this.classList.remove('spinning');
});

/* ══════════════════════════════════════════════════════════════
   CONNECTION CHECK
══════════════════════════════════════════════════════════════ */
const statusDot = document.querySelector('.status-dot');
const statusText = document.querySelector('.status-text');

async function checkConnection() {
  const { error } = await apiFetch('/api/health');
  if (error) {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'Mất kết nối';
  } else {
    statusDot.className = 'status-dot online';
    statusText.textContent = 'Đã kết nối';
  }
}
checkConnection();
setInterval(checkConnection, 30_000);

/* ══════════════════════════════════════════════════════════════
   THEME TOGGLE
══════════════════════════════════════════════════════════════ */
const themeToggleBtn = document.getElementById('themeToggleBtn');
const themeIcon = document.getElementById('themeIcon');

function setTheme(isDark) {
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  localStorage.setItem('facedf-theme', isDark ? 'dark' : 'light');

  if (isDark) {
    // Moon icon for dark mode (click to switch to light)
    themeIcon.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;
  } else {
    // Sun icon for light mode (click to switch to dark)
    themeIcon.innerHTML = `
      <circle cx="12" cy="12" r="5"></circle>
      <line x1="12" y1="1" x2="12" y2="3"></line>
      <line x1="12" y1="21" x2="12" y2="23"></line>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
      <line x1="1" y1="12" x2="3" y2="12"></line>
      <line x1="21" y1="12" x2="23" y2="12"></line>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
    `;
  }
}

// Initialize theme from localStorage or default to dark
const savedTheme = localStorage.getItem('facedf-theme') || 'dark';
setTheme(savedTheme === 'dark');

themeToggleBtn.addEventListener('click', () => {
  const isCurrentlyDark = document.documentElement.getAttribute('data-theme') !== 'light';
  setTheme(!isCurrentlyDark);
});

/* ══════════════════════════════════════════════════════════════
   DASHBOARD
══════════════════════════════════════════════════════════════ */
async function loadDashboard() {
  // Set skeleton
  ['stat-total-val', 'stat-present-val', 'stat-absent-val', 'stat-rate-val'].forEach(id => {
    const el = document.getElementById(id);
    el.textContent = '—';
    el.classList.add('skeleton');
  });

  const [statsRes, attendRes] = await Promise.all([
    apiFetch('/api/stats'),
    apiFetch('/api/attendance'),
  ]);

  /* Stats cards */
  const stats = statsRes.data;
  if (stats) {
    setStatVal('stat-total-val', stats.total_students);
    setStatVal('stat-present-val', stats.present_today);
    setStatVal('stat-absent-val', stats.absent_today);
    setStatVal('stat-rate-val', stats.attendance_rate + '%');

    const bar = document.getElementById('attendanceBar');
    bar.style.width = stats.attendance_rate + '%';
    document.getElementById('progressLabel').textContent =
      `${stats.present_today} / ${stats.total_students} sinh viên`;
    document.getElementById('progressPct').textContent = stats.attendance_rate + '%';
    document.getElementById('dash-date').textContent = fmtDate(stats.date);
  } else {
    showToast('error', 'Không tải được thống kê', statsRes.error);
  }

  /* Recent attendance table */
  const tbody = document.getElementById('recent-tbody');
  const records = attendRes.data;
  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">Chưa có điểm danh hôm nay</td></tr>`;
    return;
  }

  tbody.innerHTML = records.slice(0, 20).map((r, i) => `
    <tr>
      <td>${i + 1}</td>
      <td class="student-name">${esc(r.full_name)}</td>
      <td><span class="student-id-badge">${esc(r.student_id)}</span></td>
      <td>${fmtDateTime(r.checked_in_at)}</td>
      <td>${esc(r.device_id || '—')}</td>
      <td>${similarityCell(r.similarity)}</td>
    </tr>`).join('');
}

function setStatVal(id, val) {
  const el = document.getElementById(id);
  el.classList.remove('skeleton');
  el.textContent = val ?? '—';
}

/* ══════════════════════════════════════════════════════════════
   STUDENTS
══════════════════════════════════════════════════════════════ */
let allStudents = [];

async function loadStudents() {
  const tbody = document.getElementById('students-tbody');
  tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Đang tải...</td></tr>`;

  const { data, error } = await apiFetch('/api/students');
  if (error) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-row" style="color:var(--red)">${esc(error)}</td></tr>`;
    return;
  }

  allStudents = data || [];
  renderStudentTable(allStudents);
}

function renderStudentTable(students) {
  const tbody = document.getElementById('students-tbody');
  document.getElementById('studentCount').textContent = students.length;

  if (students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Chưa có sinh viên nào.</td></tr>`;
    return;
  }

  tbody.innerHTML = students.map((s, i) => `
    <tr data-student-id="${esc(s.student_id)}">
      <td>${i + 1}</td>
      <td><span class="student-id-badge">${esc(s.student_id)}</span></td>
      <td class="student-name">${esc(s.full_name)}</td>
      <td>${fmtDateTime(s.created_at)}</td>
      <td>
        <button class="btn-delete" onclick="openDeleteModal('${esc(s.student_id)}', '${esc(s.full_name)}')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6"/><path d="M14 11v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
          Xóa
        </button>
      </td>
    </tr>`).join('');
}

/* Student search */
document.getElementById('studentSearch').addEventListener('input', function () {
  const q = this.value.toLowerCase().trim();
  if (!q) { renderStudentTable(allStudents); return; }
  const filtered = allStudents.filter(s =>
    s.full_name.toLowerCase().includes(q) || s.student_id.toLowerCase().includes(q)
  );
  renderStudentTable(filtered);
});

/* ── Enroll Form ─────────────────────────────────────────────── */
const enrollForm = document.getElementById('enrollForm');
const inputImages = document.getElementById('inputImages');
const imagePreviews = document.getElementById('imagePreviews');
const uploadPlaceholder = document.getElementById('uploadPlaceholder');
const uploadZone = document.getElementById('uploadZone');
let selectedFiles = [];
let capturedBlobs = []; // Lưu trữ 5 ảnh chụp từ Camera
let enrollMode = 'upload'; // 'upload' hoặc 'camera'

/* Tab Switching in Enroll Form */
const btnModeUpload = document.getElementById('btnModeUpload');
const btnModeCamera = document.getElementById('btnModeCamera');
const sectionUpload = document.getElementById('sectionUpload');
const sectionCamera = document.getElementById('sectionCamera');
const piStream = document.getElementById('piStream');

function setEnrollMode(mode) {
  enrollMode = mode;
  btnModeUpload.classList.toggle('active', mode === 'upload');
  btnModeCamera.classList.toggle('active', mode === 'camera');
  sectionUpload.classList.toggle('active', mode === 'upload');
  sectionCamera.classList.toggle('active', mode === 'camera');

  if (mode === 'camera') {
    startPiStream();
  } else {
    stopPiStream();
  }
}

btnModeUpload.addEventListener('click', () => setEnrollMode('upload'));
btnModeCamera.addEventListener('click', () => setEnrollMode('camera'));

const inputPiIp = document.getElementById('inputPiIp');
const btnApplyIp = document.getElementById('btnApplyIp');

// Init IP input from storage
inputPiIp.value = PI_IP;

btnApplyIp.addEventListener('click', () => {
  const ip = inputPiIp.value.trim();
  if (ip) {
    PI_IP = ip;
    localStorage.setItem('pi-ip', ip);
    showToast('success', 'Đã lưu IP', `Đang kết nối tới ${ip}...`);
    if (enrollMode === 'camera') startPiStream();
  } else {
    showToast('error', 'Lỗi', 'Vui lòng nhập địa chỉ IP.');
  }
});

function startPiStream() {
  piStream.crossOrigin = "anonymous"; // Cho phép canvas đọc dữ liệu từ IP khác
  piStream.src = `http://${PI_IP}:8080/raw?t=${Date.now()}`; // Thêm timestamp để tránh cache
}
function stopPiStream() {
  piStream.src = '';
}

document.getElementById('btnReloadStream').addEventListener('click', () => {
  showToast('info', 'Đang tải lại...', 'Đang làm mới luồng camera.');
  startPiStream();
});

/* Collapse/expand form */
const enrollBody = document.getElementById('enrollBody');
const toggleBtn = document.getElementById('toggleEnroll');
let enrollCollapsed = false;
toggleBtn.addEventListener('click', () => {
  enrollCollapsed = !enrollCollapsed;
  enrollBody.style.display = enrollCollapsed ? 'none' : '';
  toggleBtn.classList.toggle('collapsed', enrollCollapsed);
});

/* Drag & Drop */
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  handleFiles([...e.dataTransfer.files]);
});

inputImages.addEventListener('change', () => handleFiles([...inputImages.files]));

function handleFiles(files) {
  const imgs = files.filter(f => f.type.startsWith('image/'));
  if (imgs.length === 0) return;
  selectedFiles = [...selectedFiles, ...imgs].slice(0, 5);
  renderPreviews();
}

function renderPreviews() {
  if (selectedFiles.length === 0) {
    uploadPlaceholder.style.display = '';
    imagePreviews.innerHTML = '';
    return;
  }
  uploadPlaceholder.style.display = 'none';
  imagePreviews.innerHTML = selectedFiles.map((f, i) => {
    const url = URL.createObjectURL(f);
    return `<div class="preview-thumb">
      <img src="${url}" alt="Preview ${i + 1}" />
      <button class="preview-remove" onclick="removePreview(${i})" aria-label="Xóa ảnh">✕</button>
    </div>`;
  }).join('');
}

function removePreview(idx) {
  selectedFiles.splice(idx, 1);
  renderPreviews();
}

/* Camera Capture Logic */
const btnCapture = document.getElementById('btnCapture');
const capturedList = document.getElementById('capturedList');
const captureCountLabel = document.getElementById('captureCountLabel');
const progressFill = document.getElementById('captureProgressFill');

btnCapture.addEventListener('click', captureFromPi);

async function captureFromPi() {
  if (capturedBlobs.length >= 5) {
    showToast('warning', 'Đã đủ 5 ảnh', 'Bạn đã chụp đủ số lượng ảnh cần thiết.');
    return;
  }

  // Hiệu ứng nháy màn hình khi chụp
  piStream.style.opacity = '0.5';
  setTimeout(() => piStream.style.opacity = '1', 100);

  try {
    const blob = await snapFrame(piStream);
    capturedBlobs.push(blob);
    renderCapturedList();
  } catch (e) {
    showToast('error', 'Lỗi chụp ảnh', 'Không thể lấy dữ liệu từ luồng Camera.');
  }
}

function snapFrame(imgEl) {
  return new Promise((resolve) => {
    const canvas = document.createElement('canvas');
    canvas.width = imgEl.naturalWidth || 640;
    canvas.height = imgEl.naturalHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(imgEl, 0, 0);
    canvas.toBlob(resolve, 'image/jpeg', 0.9);
  });
}

function renderCapturedList() {
  capturedList.innerHTML = capturedBlobs.map((blob, i) => {
    const url = URL.createObjectURL(blob);
    return `
      <div class="captured-item">
        <img src="${url}" />
        <button type="button" class="btn-retake" onclick="retakePhoto(${i})">Chụp lại</button>
      </div>`;
  }).join('');

  const count = capturedBlobs.length;
  captureCountLabel.textContent = `Đã chụp: ${count}/5`;
  progressFill.style.width = `${(count / 5) * 100}%`;
}

window.retakePhoto = (idx) => {
  capturedBlobs.splice(idx, 1);
  renderCapturedList();
};

document.getElementById('resetEnrollBtn').addEventListener('click', resetEnrollForm);
function resetEnrollForm() {
  enrollForm.reset();
  selectedFiles = [];
  capturedBlobs = [];
  renderPreviews();
  renderCapturedList();
  setEnrollMode('upload');
}

enrollForm.addEventListener('submit', async e => {
  e.preventDefault();

  const fullName = document.getElementById('inputFullName').value.trim();
  const studentId = document.getElementById('inputStudentId').value.trim();

  if (!fullName || !studentId) {
    showToast('error', 'Thiếu thông tin', 'Vui lòng nhập đầy đủ họ tên và MSSV.');
    return;
  }

  let filesToUpload = [];
  if (enrollMode === 'upload') {
    if (selectedFiles.length < 3) {
      showToast('error', 'Thiếu ảnh', `Cần ít nhất 3 ảnh, bạn đã chọn ${selectedFiles.length}.`);
      return;
    }
    filesToUpload = selectedFiles;
  } else {
    if (capturedBlobs.length < 3) {
      showToast('error', 'Thiếu ảnh', `Cần ít nhất 3 ảnh từ Camera, bạn mới chụp ${capturedBlobs.length}.`);
      return;
    }
    filesToUpload = capturedBlobs;
  }

  const btn = document.getElementById('enrollSubmitBtn');
  btn.disabled = true;
  btn.innerHTML = `<span class="loading-spinner" style="width:16px;height:16px;border-width:2px"></span> Đang xử lý...`;
  showLoading();

  const fd = new FormData();
  fd.append('full_name', fullName);
  fd.append('student_id', studentId);

  if (enrollMode === 'upload') {
    filesToUpload.forEach(f => fd.append('images', f));
  } else {
    // Với camera blobs, ta đặt tên file giả định
    filesToUpload.forEach((blob, i) => {
      fd.append('images', blob, `cam_capture_${i}.jpg`);
    });
  }

  const { data, error } = await apiFetch('/api/students', { method: 'POST', body: fd });
  hideLoading();
  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg> Đăng ký sinh viên`;

  if (error) {
    showToast('error', 'Đăng ký thất bại', error);
    return;
  }

  showToast('success', 'Đăng ký thành công!', `${data.full_name} (${data.student_id}) — ${data.images_processed} ảnh được xử lý.`);
  resetEnrollForm();
  loadStudents();
});

/* ══════════════════════════════════════════════════════════════
   DELETE MODAL
══════════════════════════════════════════════════════════════ */
const deleteModal = document.getElementById('deleteModal');
const deleteModalMsg = document.getElementById('deleteModalMsg');
const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
let _pendingDeleteId = null;

function openDeleteModal(studentId, fullName) {
  _pendingDeleteId = studentId;
  deleteModalMsg.textContent =
    `Bạn có chắc muốn xóa sinh viên "${fullName}" (${studentId})? ` +
    `Toàn bộ dữ liệu điểm danh sẽ bị xóa vĩnh viễn.`;
  deleteModal.classList.add('active');
}

function closeDeleteModal() {
  deleteModal.classList.remove('active');
  _pendingDeleteId = null;
}

cancelDeleteBtn.addEventListener('click', closeDeleteModal);
deleteModal.addEventListener('click', e => { if (e.target === deleteModal) closeDeleteModal(); });

confirmDeleteBtn.addEventListener('click', async () => {
  if (!_pendingDeleteId) return;
  const id = _pendingDeleteId;
  closeDeleteModal();
  showLoading();

  const { error } = await apiFetch(`/api/students/${encodeURIComponent(id)}`, { method: 'DELETE' });
  hideLoading();

  if (error) {
    showToast('error', 'Xóa thất bại', error);
    return;
  }

  showToast('success', 'Đã xóa sinh viên', `Sinh viên ${id} đã được xóa khỏi hệ thống.`);
  loadStudents();
});

/* ══════════════════════════════════════════════════════════════
   ATTENDANCE
══════════════════════════════════════════════════════════════ */
const attendanceDateInput = document.getElementById('attendanceDate');
let _currentAttendance = [];

// Set date input to today
attendanceDateInput.value = todayISO();
attendanceDateInput.max = todayISO();

attendanceDateInput.addEventListener('change', () => {
  loadAttendanceForDate(attendanceDateInput.value);
});

document.getElementById('todayBtn').addEventListener('click', () => {
  attendanceDateInput.value = todayISO();
  loadAttendanceForDate(todayISO());
});

async function loadAttendanceForDate(dateStr) {
  const tbody = document.getElementById('attendance-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="empty-row">Đang tải...</td></tr>`;
  document.getElementById('attendanceSummary').innerHTML = '';

  const url = `/api/attendance?date=${dateStr}`;
  const { data, error } = await apiFetch(url);

  if (error) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row" style="color:var(--red)">${esc(error)}</td></tr>`;
    return;
  }

  _currentAttendance = data || [];
  renderAttendanceTable(_currentAttendance, dateStr);
}

function renderAttendanceTable(records, dateStr) {
  const tbody = document.getElementById('attendance-tbody');
  const summary = document.getElementById('attendanceSummary');

  // Summary bar
  summary.innerHTML = `
    <div class="att-stat">📅 <strong>${fmtDate(dateStr)}</strong></div>
    <div class="att-stat">✅ Có mặt: <strong>${records.length}</strong></div>
  `;

  if (records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row">Không có điểm danh vào ngày ${fmtDate(dateStr)}</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map((r, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><span class="student-id-badge">${esc(r.student_id)}</span></td>
      <td class="student-name">${esc(r.full_name)}</td>
      <td>${fmtDateTime(r.checked_in_at)}</td>
      <td>${esc(r.device_id || '—')}</td>
      <td>${similarityCell(r.similarity)}</td>
      <td><span class="badge-present">✓ Có mặt</span></td>
    </tr>`).join('');
}

/* Export CSV */
document.getElementById('exportCsvBtn').addEventListener('click', () => {
  if (_currentAttendance.length === 0) {
    showToast('info', 'Không có dữ liệu', 'Chọn ngày có dữ liệu điểm danh trước.');
    return;
  }
  const dateStr = attendanceDateInput.value || todayISO();
  const headers = ['STT', 'MSSV', 'Họ và tên', 'Thời gian', 'Thiết bị', 'Độ tin cậy'];
  const rows = _currentAttendance.map((r, i) =>
    [i + 1, r.student_id, r.full_name, fmtDateTime(r.checked_in_at), r.device_id, r.similarity].join(',')
  );
  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `diem-danh-${dateStr}.csv`;
  link.click();
  showToast('success', 'Xuất CSV thành công', `${_currentAttendance.length} bản ghi.`);
});

/* ══════════════════════════════════════════════════════════════
   SHARED HELPERS
══════════════════════════════════════════════════════════════ */
function esc(str) {
  if (str == null) return '';
  return String(str).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function similarityCell(sim) {
  const pct = Math.round(sim || 0);
  return `<div class="similarity-bar">
    <div class="similarity-track"><div class="similarity-fill" style="width:${pct}%"></div></div>
    <span class="similarity-text">${pct}%</span>
  </div>`;
}

/* ══════════════════════════════════════════════════════════════
   M3 EXTENSIONS: EXCEL EXPORT, REPORT TAB, LOGOUT
══════════════════════════════════════════════════════════════ */

// Đăng ký sự kiện nút Đăng xuất
document.getElementById('logoutBtn')?.addEventListener('click', () => {
  if (confirm('Bạn có chắc muốn đăng xuất khỏi hệ thống?')) {
    logout();
  }
});

// Nút Xuất Excel trong tab Điểm danh
document.getElementById('exportExcelBtn')?.addEventListener('click', async () => {
  const dateStr = attendanceDateInput?.value || todayISO();
  const token = localStorage.getItem('access_token');
  try {
    showLoading();
    const res = await fetch(`${API}/api/attendance/export/excel?date=${dateStr}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast('error', 'Lỗi xuất Excel', err.detail || 'Không thể tạo file');
      return;
    }
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `diem-danh-${dateStr}.xlsx`;
    link.click();
    showToast('success', 'Xuất Excel thành công', `Tải về file diem-danh-${dateStr}.xlsx`);
  } catch (e) {
    showToast('error', 'Lỗi', e.message);
  } finally {
    hideLoading();
  }
});

// Tải dữ liệu Tab Báo cáo
async function loadReport(dateStr) {
  dateStr = dateStr || todayISO();
  const dateEl = document.getElementById('reportDate') || document.getElementById('reportDateInput');
  if (dateEl) dateEl.value = dateStr;

  const { data, error } = await apiFetch(`/api/attendance/summary?date=${dateStr}`);
  if (error || !data) {
    showToast('error', 'Lỗi tải báo cáo', error);
    return;
  }

  // Cập nhật các thẻ tóm tắt (hỗ trợ cả 2 bộ id rpt-* và rep-*)
  const setVal = (ids, val) => {
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = val ?? 0;
    });
  };

  setVal(['rpt-total-checkin', 'rep-checkin'], data.total_checkin);
  setVal(['rpt-on-time', 'rep-ontime'], data.on_time);
  setVal(['rpt-late', 'rep-late'], data.late);
  setVal(['rpt-early-leave', 'rep-early'], data.early_leave);

  const badgeDate = document.getElementById('reportDateBadge');
  if (badgeDate) badgeDate.textContent = fmtDate(dateStr);

  // Render bảng chi tiết ca làm việc
  const tbody = document.getElementById('report-tbody');
  if (!tbody) return;

  if (!data.details || data.details.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row">Không có dữ liệu điểm danh ngày ${fmtDate(dateStr)}</td></tr>`;
    return;
  }

  tbody.innerHTML = data.details.map((d, i) => {
    let statusBadge = '<span class="status-pill status-present">Đúng giờ</span>';
    if (d.status === 'late') {
      statusBadge = '<span class="status-pill" style="background:rgba(234,179,8,0.15);color:#eab308;border:1px solid rgba(234,179,8,0.3)">Đi muộn</span>';
    } else if (d.status === 'early_leave') {
      statusBadge = '<span class="status-pill status-absent">Về sớm</span>';
    }

    const typeStr = d.check_out_time ? 'Ra (Check-out)' : 'Vào (Check-in)';
    const timeDisplay = d.check_out_time ? fmtDateTime(d.check_out_time) : (d.check_in_time ? fmtDateTime(d.check_in_time) : '—');

    return `
      <tr>
        <td>${i + 1}</td>
        <td><strong>${esc(d.student_id)}</strong></td>
        <td>${esc(d.full_name)}</td>
        <td><span class="badge" style="background:rgba(99,102,241,0.15);color:#818cf8">${typeStr}</span></td>
        <td>${timeDisplay}</td>
        <td>${statusBadge}</td>
        <td>${esc(d.device_id || 'Raspi_01')}</td>
      </tr>
    `;
  }).join('');
}

// Tải thông tin cấu hình ca làm việc
async function loadShiftSettings() {
  const { data, error } = await apiFetch('/api/tenant/shift');
  if (error || !data) return;

  const startIn = document.getElementById('shiftStartInput');
  const endIn = document.getElementById('shiftEndInput');
  const badge = document.getElementById('shiftTenantBadge');

  if (startIn) startIn.value = data.shift_start || '08:00';
  if (endIn) endIn.value = data.shift_end || '17:00';
  if (badge) badge.textContent = `${data.tenant_code} (${data.shift_start} - ${data.shift_end})`;
}

// Bắt sự kiện lưu cấu hình ca làm việc
document.getElementById('shiftConfigForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const shiftStart = document.getElementById('shiftStartInput').value;
  const shiftEnd = document.getElementById('shiftEndInput').value;
  const msgEl = document.getElementById('shiftStatusMsg');

  if (!shiftStart || !shiftEnd) {
    showToast('warning', 'Thiếu dữ liệu', 'Vui lòng chọn cả giờ vào và giờ ra');
    return;
  }

  showLoading();
  const { data, error } = await apiFetch('/api/tenant/shift', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ shift_start: shiftStart, shift_end: shiftEnd })
  });
  hideLoading();

  if (error) {
    showToast('error', 'Lỗi lưu ca', error);
  } else {
    showToast('success', 'Thành công', 'Đã cập nhật ca làm việc mới!');
    if (msgEl) {
      msgEl.textContent = '✅ Đã lưu thay đổi';
      setTimeout(() => { msgEl.textContent = ''; }, 3000);
    }
    loadShiftSettings();
  }
});

// Bắt sự kiện lọc ngày trên Tab Báo cáo
document.getElementById('reportDate')?.addEventListener('change', (e) => {
  loadReport(e.target.value);
});
document.getElementById('loadReportBtn')?.addEventListener('click', () => {
  const dt = document.getElementById('reportDate')?.value || todayISO();
  loadReport(dt);
});
document.getElementById('reportTodayBtn')?.addEventListener('click', () => {
  const today = todayISO();
  const inp = document.getElementById('reportDate');
  if (inp) inp.value = today;
  loadReport(today);
});

/* ══════════════════════════════════════════════════════════════
   AUTO REFRESH (every 30 sec on dashboard)
══════════════════════════════════════════════════════════════ */
setInterval(() => {
  const active = document.querySelector('.tab-content.active')?.id;
  if (active === 'tab-dashboard') loadDashboard();
}, 30_000);

/* ══════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════ */
switchTab('dashboard');
