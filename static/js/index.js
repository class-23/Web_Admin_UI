var cachedDevices = [];
var selectedDeviceMac = '';
var probeInProgress = false;
var pendingDeleteMac = null;
var confirmTimer = null;

function getDisplayDeviceName(device, index) {
    return device.hostname || device.mac || ('设备' + (index + 1));
}

function getSelectedDevice() {
    if (!selectedDeviceMac) return null;
    return cachedDevices.find(function(device) {
        return device.mac === selectedDeviceMac;
    }) || null;
}

function showToast(message, type) {
    var toast = document.getElementById('global-toast');
    if (!toast) return;
    var styles = {
        info: 'border-blue-100 bg-blue-50 text-blue-700',
        success: 'border-green-100 bg-green-50 text-green-700',
        warning: 'border-yellow-100 bg-yellow-50 text-yellow-700',
        error: 'border-red-100 bg-red-50 text-red-700'
    };
    toast.textContent = message;
    toast.className = 'fixed right-4 top-4 z-50 max-w-sm rounded-lg border px-4 py-3 text-sm shadow-lg toast-enter ' + (styles[type] || styles.info);
    toast.classList.remove('hidden');
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(function() {
        toast.classList.add('hidden');
    }, 3200);
}

function handleFileManagerClick() {
    if (!ensureDeviceSelected(true)) {
        return;
    }
    window.location.href = '/file_manager';
}

function getStatusBadge(device) {
    if (device.isOnline === true) {
        return '<span class="px-3 py-1 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-600 flex items-center gap-1.5 border border-emerald-100 shadow-sm"><span class="relative flex h-1.5 w-1.5"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span></span>在线</span>';
    } else if (device.isOnline === false) {
        return '<span class="px-3 py-1 rounded-lg text-xs font-bold bg-slate-100 text-slate-500 flex items-center gap-1.5 border border-slate-200 shadow-sm"><span class="w-1.5 h-1.5 rounded-full bg-slate-400 shadow-inner"></span>离线</span>';
    }
    return '<span class="px-3 py-1 rounded-lg text-xs font-bold bg-gray-100 text-gray-500 flex items-center gap-1.5 border border-gray-200 shadow-sm"><span class="w-1.5 h-1.5 rounded-full bg-gray-400 shadow-inner"></span>未知</span>';
}

function getStatusText(device) {
    if (!device) return '未选择';
    if (device.isOnline === true) return '在线';
    if (device.isOnline === false) return '离线';
    return '未知';
}

function getActionHint(device) {
    if (!cachedDevices.length) {
        return '当前还没有已注册设备，请先让设备完成注册上报。';
    }
    if (!device) {
        return '请选择一台已注册设备后，再进入控制面板、终端或文件管理。';
    }
    if (!device.lastIp) {
        return '当前设备尚未上报有效 IP，暂时无法打开控制面板或终端。';
    }
    if (device.isOnline === false) {
        return '当前设备显示离线，仍可尝试访问，但可能会连接失败。';
    }
    return '当前设备已就绪，可直接进入控制面板或终端。';
}

function updateActionCards(device) {
    var controlCard = document.getElementById('control-panel-card');
    var terminalCard = document.getElementById('terminal-card');
    var fileCard = document.getElementById('file-manager-card');
    var hasDevice = !!device;
    var hasIp = !!(device && device.lastIp);
    var disableControlAndTerminal = !hasDevice || !hasIp || probeInProgress;
    var disableFile = !hasDevice;

    [controlCard, terminalCard].forEach(function(card) {
        if (!card) return;
        card.disabled = disableControlAndTerminal;
        card.classList.toggle('action-card-disabled', disableControlAndTerminal);
    });

    if (fileCard) {
        fileCard.disabled = disableFile;
        fileCard.classList.toggle('action-card-disabled', disableFile);
    }
}

function updateSelectedDeviceSummary(device) {
    var nameEl = document.getElementById('selected-device-name');
    var ipEl = document.getElementById('selected-device-ip');
    var statusEl = document.getElementById('selected-device-status');
    var hintEl = document.getElementById('device-action-hint');

    if (nameEl) nameEl.textContent = device ? (device.hostname || device.mac || '未命名设备') : '未选择设备';
    if (ipEl) ipEl.textContent = device && device.lastIp ? device.lastIp : '-';

    if (statusEl) {
        if (device && device.isOnline === true) {
            statusEl.innerHTML = '<span class="relative flex h-1.5 w-1.5"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span></span> 在线';
            statusEl.className = 'px-2.5 py-0.5 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-600 flex items-center gap-1.5 border border-emerald-100 shadow-sm';
        } else if (device && device.isOnline === false) {
            statusEl.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-slate-400 shadow-inner"></span> 离线';
            statusEl.className = 'px-2.5 py-0.5 rounded-md text-xs font-semibold bg-slate-100 text-slate-500 flex items-center gap-1.5 border border-slate-200 shadow-sm';
        } else {
            statusEl.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-slate-400 shadow-inner"></span> 未选择';
            statusEl.className = 'px-2.5 py-0.5 rounded-md text-xs font-semibold bg-slate-200 text-slate-600 flex items-center gap-1.5 shadow-inner';
        }
    }

    if (hintEl) {
        var hintText = getActionHint(device);
        var hintBaseClasses = 'text-sm px-4 py-3 rounded-xl flex items-start gap-3 xl:max-w-md shadow-sm backdrop-blur-sm';
        var colorClasses, iconHtml;
        if (!device || !device.lastIp) {
            colorClasses = 'bg-yellow-50/80 border border-yellow-200/60 text-yellow-700';
            iconHtml = '<div class="bg-yellow-100 text-yellow-500 rounded-full p-1 shrink-0 mt-0.5"><i class="ri-error-warning-fill text-base leading-none"></i></div>';
        } else if (device.isOnline === false) {
            colorClasses = 'bg-orange-50/80 border border-orange-200/60 text-orange-700';
            iconHtml = '<div class="bg-orange-100 text-orange-500 rounded-full p-1 shrink-0 mt-0.5"><i class="ri-error-warning-fill text-base leading-none"></i></div>';
        } else {
            colorClasses = 'bg-blue-50/80 border border-blue-200/60 text-blue-700';
            iconHtml = '<div class="bg-blue-100 text-blue-500 rounded-full p-1 shrink-0 mt-0.5"><i class="ri-information-line text-base leading-none"></i></div>';
        }
        hintEl.className = hintBaseClasses + ' ' + colorClasses;
        hintEl.innerHTML = iconHtml + '<p class="leading-relaxed font-medium">' + hintText + '</p>';
    }
}

function updateDeviceSelector(devices) {
    var selector = document.getElementById('device-selector');
    if (!selector) return;

    var previousMac = selectedDeviceMac;
    var nextSelectedMac = '';

    if (previousMac && devices.some(function(device) { return device.mac === previousMac; })) {
        nextSelectedMac = previousMac;
    } else {
        var onlineDevice = devices.find(function(device) { return device.isOnline === true; });
        nextSelectedMac = onlineDevice ? onlineDevice.mac : (devices[0] ? devices[0].mac : '');
    }

    var options = '<option value="">请选择已注册设备</option>';
    devices.forEach(function(device, index) {
        var deviceName = getDisplayDeviceName(device, index);
        var suffix = device.lastIp ? ' · ' + device.lastIp : '';
        options += '<option value="' + device.mac + '">' + deviceName + suffix + '</option>';
    });
    selector.innerHTML = options;
    selector.value = nextSelectedMac;
    selector.disabled = devices.length === 0;
    selectedDeviceMac = nextSelectedMac;
    updateSelectedDeviceSummary(getSelectedDevice());
    updateActionCards(getSelectedDevice());
}

function renderDevices(devices) {
    var container = document.getElementById('device-info-content');
    if (!container) return;

    if (!devices || devices.length === 0) {
        renderEmptyDeviceState();
        container.innerHTML = '<div class="flex flex-col items-center justify-center py-12 text-gray-400 col-span-full"><i class="ri-computer-line text-4xl mb-3 text-gray-300"></i><p class="text-sm">暂无设备</p></div>';
        return;
    }

    var html = '';
    devices.forEach(function(device, index) {
        var deviceName = getDisplayDeviceName(device, index);
        var lastIp = device.lastIp || '-';
        var lastSsid = device.lastSsid || '-';
        var mac = device.mac || '-';
        var model = device.model || '-';
        var firmware = device.firmwareVersion || '-';
        var isOnline = device.isOnline === true;
        var offlineClass = !isOnline ? ' grayscale-[30%] opacity-80' : '';
        var headerBg = isOnline ? 'bg-gradient-to-r from-slate-50 to-white' : 'bg-slate-50/50';
        var headerOpacity = !isOnline ? ' opacity-80' : '';

        html += '<div class="bg-white rounded-2xl shadow-sm border border-slate-200/80 overflow-hidden flex flex-col hover:shadow-lg transition-all' + offlineClass + '">' +
            '<div class="px-5 py-4 border-b border-slate-100 flex justify-between items-center ' + headerBg + '">' +
                '<div class="flex items-center gap-2 font-bold text-slate-800 text-lg' + headerOpacity + '">' +
                    '<i class="ri-router-line text-slate-400 font-normal"></i> ' + deviceName +
                '</div>' +
                getStatusBadge(device) +
            '</div>' +
            '<div class="p-5 flex-1 bg-white">' +
                '<div class="space-y-4">' +
                    '<div class="flex justify-between items-center text-sm border-b border-slate-50 pb-2 border-dashed">' +
                        '<span class="text-slate-500 flex items-center gap-1.5"><i class="ri-barcode-box-line text-slate-400"></i> MAC 地址</span>' +
                        '<span class="text-slate-700 font-mono text-xs bg-slate-50 px-2 py-1 rounded-md font-semibold border border-slate-100 uppercase">' + mac + '</span>' +
                    '</div>' +
                    '<div class="flex justify-between items-center text-sm border-b border-slate-50 pb-2 border-dashed">' +
                        '<span class="text-slate-500 flex items-center gap-1.5"><i class="ri-global-line text-slate-400"></i> 最后 IP</span>' +
                        '<span class="' + (lastIp === '-' ? 'text-slate-400' : 'text-slate-800') + ' font-mono font-semibold">' + lastIp + '</span>' +
                    '</div>' +
                    '<div class="flex justify-between items-center text-sm border-b border-slate-50 pb-2 border-dashed">' +
                        '<span class="text-slate-500 flex items-center gap-1.5"><i class="' + (lastSsid === '-' ? 'ri-wifi-off-line' : 'ri-wifi-line') + ' text-slate-400"></i> Wi-Fi SSID</span>' +
                        '<span class="' + (lastSsid === '-' ? 'text-slate-400 italic' : 'text-slate-800') + ' font-medium">' + (lastSsid === '-' ? '未连接' : lastSsid) + '</span>' +
                    '</div>' +
                    '<div class="flex justify-between items-center text-sm border-b border-slate-50 pb-2 border-dashed">' +
                        '<span class="text-slate-500 flex items-center gap-1.5"><i class="ri-cpu-line text-slate-400"></i> 设备型号</span>' +
                        '<span class="' + (model === '-' ? 'text-slate-400' : 'text-slate-800') + ' font-medium">' + model + '</span>' +
                    '</div>' +
                    '<div class="flex justify-between items-center text-sm pb-1">' +
                        '<span class="text-slate-500 flex items-center gap-1.5"><i class="ri-git-merge-line text-slate-400"></i> 固件版本</span>' +
                        '<span class="' + (firmware === '-' ? 'text-slate-400' : 'text-slate-800') + ' font-medium bg-blue-50 text-blue-600 px-2 py-0.5 rounded-md text-xs border border-blue-100 font-mono">' + firmware + '</span>' +
                    '</div>' +
                '</div>' +
            '</div>' +
            '<div class="px-5 py-3 border-t border-slate-100 bg-slate-50/50 flex gap-2">' +
                '<button onclick="fetchDevices()" class="flex-1 py-2.5 flex items-center justify-center gap-2 text-sm font-semibold text-slate-600 hover:text-rose-600 bg-white border border-slate-200 rounded-xl shadow-sm hover:shadow hover:border-rose-200 transition-all active:scale-[0.98]">' +
                    '<i class="ri-refresh-line text-lg leading-none"></i> 刷新' +
                '</button>' +
                (pendingDeleteMac === mac
                    ? '<button onclick="performDelete(\'' + mac + '\')" class="flex-1 py-2.5 flex items-center justify-center gap-2 text-sm font-semibold text-white bg-red-500 hover:bg-red-600 border border-red-500 rounded-xl shadow-sm transition-all active:scale-[0.98]"><i class="ri-alert-line text-lg leading-none"></i> 确认删除</button>'
                    : '<button onclick="handleDeleteDevice(\'' + mac + '\')" class="py-2.5 px-3 flex items-center justify-center text-sm text-slate-400 hover:text-red-500 bg-white border border-slate-200 rounded-xl shadow-sm hover:shadow hover:border-red-200 transition-all active:scale-[0.98]"><i class="ri-delete-bin-line text-lg leading-none"></i></button>'
                ) +
            '</div>' +
        '</div>';
    });

    container.innerHTML = html;
}

function renderEmptyDeviceState() {
    cachedDevices = [];
    selectedDeviceMac = '';
    updateDeviceSelector([]);
    updateSelectedDeviceSummary(null);
    updateActionCards(null);
}

function renderError(message) {
    var container = document.getElementById('device-info-content');
    if (!container) return;
    renderEmptyDeviceState();
    container.innerHTML = '<div class="flex flex-col items-center justify-center py-8 text-gray-400 col-span-full">' +
        '<i class="ri-alert-line text-4xl mb-3 text-yellow-400"></i>' +
        '<p class="text-sm">' + message + '</p>' +
        '<button onclick="fetchDevices()" class="mt-3 px-4 py-1.5 text-xs bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">重新加载</button>' +
        '</div>';
}

async function fetchDevices() {
    var container = document.getElementById('device-info-content');
    if (container) {
        container.innerHTML = '<div class="flex items-center justify-center py-8 col-span-full">' +
            '<div class="loading-spinner mr-3"></div>' +
            '<p class="text-gray-400">正在加载设备信息...</p>' +
            '</div>';
    }

    try {
        var response = await fetch('/api/devices');
        if (response.status === 401) {
            renderError('登录后可查看设备信息');
            return;
        }
        if (!response.ok) {
            throw new Error('服务器响应异常（状态码：' + response.status + '）');
        }
        var result = await response.json();
        if (result.code === 0) {
            cachedDevices = Array.isArray(result.data && result.data.devices) ? result.data.devices : [];
            updateDeviceSelector(cachedDevices);
            renderDevices(cachedDevices);
        } else {
            renderError('获取设备列表失败：' + (result.message || '未知错误'));
        }
    } catch (error) {
        console.error('获取设备列表失败:', error);
        renderError('无法连接到服务器，请检查网络连接');
    }
}

function handleDeviceSelectionChange(mac) {
    selectedDeviceMac = mac;
    var selectedDevice = getSelectedDevice();
    updateSelectedDeviceSummary(selectedDevice);
    updateActionCards(selectedDevice);
}

function ensureDeviceSelected(showTip) {
    var selectedDevice = getSelectedDevice();
    if (!selectedDevice) {
        if (showTip) {
            showToast('请先选择一台已注册设备。', 'warning');
        }
        return null;
    }
    return selectedDevice;
}

function normalizeDeviceModel(model) {
    return String(model || '')
        .trim()
        .toLowerCase()
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ');
}

function isHinlinkHt2Model(model) {
    var normalized = normalizeDeviceModel(model);
    return normalized === 'hinlink ht2' || normalized.indexOf('hinlink ht2 ') === 0;
}

function getControlPanelPort(device) {
    return isHinlinkHt2Model(device && device.model) ? 42617 : 6060;
}

function handleControlPanelClick() {
    var device = ensureDeviceSelected(true);
    if (!device) {
        return;
    }
    if (!device.lastIp) {
        showToast('当前设备尚未上报有效 IP，无法打开控制面板。', 'warning');
        return;
    }

    var port = getControlPanelPort(device);
    var targetUrl = 'http://' + device.lastIp + ':' + port;

    probeInProgress = true;
    updateActionCards(device);
    showToast('正在打开设备控制面板...', 'info');

    try {
        window.open(targetUrl, '_blank', 'noopener');
        showToast('已打开设备控制面板。', 'success');
    } finally {
        probeInProgress = false;
        updateActionCards(device);
    }
}

function handleTerminalClick() {
    var device = ensureDeviceSelected(true);
    if (!device) {
        return;
    }
    if (!device.lastIp) {
        showToast('当前设备尚未上报有效 IP，无法打开终端。', 'warning');
        return;
    }
    window.open('http://' + device.lastIp + ':7681', '_blank', 'noopener');
}

function handleLogout() {
    fetch('/api/logout', {
        method: 'POST',
        credentials: 'include'
    })
    .then(function() {
        localStorage.removeItem('username');
        window.location.reload();
    })
    .catch(function() {
        localStorage.removeItem('username');
        window.location.reload();
    });
}

async function checkLoginStatus() {
    var unauthDiv = document.getElementById('unauth-buttons');
    var authDiv = document.getElementById('auth-user-info');
    var displayName = document.getElementById('display-username');

    try {
        var res = await fetch('/api/current_user', { credentials: 'include' });
        if (!res.ok && res.status === 401) {
            window.location.href = '/login?reason=password_changed';
            return false;
        }
        var data = await res.json();
        if (data.code === 0 && data.data && data.data.username) {
            var username = data.data.username;
            if (unauthDiv) unauthDiv.style.display = 'none';
            if (authDiv) authDiv.style.display = 'flex';
            if (displayName) displayName.textContent = username;
            if (!localStorage.getItem('username')) {
                localStorage.setItem('username', username);
            }
            return true;
        }
    } catch (e) {
        console.error('Check login failed:', e);
    }
    if (unauthDiv) unauthDiv.style.display = 'flex';
    if (authDiv) authDiv.style.display = 'none';
    return false;
}

function requireLogin(targetUrl) {
    var username = localStorage.getItem('username');
    if (username) {
        window.location.href = targetUrl;
    } else {
        window.location.href = '/login';
    }
}

async function init() {
    var unauthDiv = document.getElementById('unauth-buttons');
    var authDiv = document.getElementById('auth-user-info');
    if (unauthDiv) unauthDiv.style.display = 'flex';
    if (authDiv) authDiv.style.display = 'none';
    var isLoggedIn = await checkLoginStatus();
    if (isLoggedIn) {
        fetchDevices();
        setInterval(fetchDevices, 30000);
    } else {
        renderError('登录后可查看设备信息');
    }
}

function handleDeleteDevice(mac) {
    if (pendingDeleteMac === mac) {
        return;
    }
    pendingDeleteMac = mac;
    clearTimeout(confirmTimer);
    confirmTimer = setTimeout(function() {
        pendingDeleteMac = null;
        renderDevices(cachedDevices);
    }, 3000);
    renderDevices(cachedDevices);
}

async function performDelete(mac) {
    clearTimeout(confirmTimer);
    pendingDeleteMac = null;
    try {
        var response = await fetch('/api/devices/' + encodeURIComponent(mac), {
            method: 'DELETE',
            credentials: 'include'
        });
        if (response.status === 401) {
            showToast('请先登录后再删除设备', 'warning');
            renderDevices(cachedDevices);
            return;
        }
        if (!response.ok) {
            var data = await response.json().catch(function() { return {}; });
            throw new Error(data.message || '删除失败（状态码：' + response.status + '）');
        }
        showToast('设备已删除', 'success');
        fetchDevices();
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
        renderDevices(cachedDevices);
    }
}

window.addEventListener('DOMContentLoaded', init);
