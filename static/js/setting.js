var PASSWORD_MIN_LENGTH = 8;

// ========== Auth Intercept ==========
(function() {
    var nativeFetch = window.fetch;
    window.fetch = function() {
        return nativeFetch.apply(this, arguments).then(function(response) {
            if (response.status === 401) {
                localStorage.removeItem('username');
                window.location.href = '/login?reason=password_changed';
                return new Promise(function() {});
            }
            return response;
        });
    };
})();

// ========== Toast ==========
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

// ========== Password Functions ==========
window.togglePasswordVisibility = function(inputId) {
    var input = document.getElementById(inputId);
    var eyeIcon = document.getElementById(inputId + '-eye-icon');
    if (!input || !eyeIcon) return;
    if (input.type === 'password') {
        input.type = 'text';
        eyeIcon.textContent = '👁️';
    } else {
        input.type = 'password';
        eyeIcon.textContent = '🙈';
    }
};

window.checkPasswordRequirements = function(password) {
    var hasMinLength = password.length >= PASSWORD_MIN_LENGTH;
    var hasLetter = /[a-zA-Z]/.test(password);
    var hasNumber = /[0-9]/.test(password);
    return { hasMinLength: hasMinLength, hasLetter: hasLetter, hasNumber: hasNumber };
};

window.calculatePasswordStrength = function(password) {
    if (!password) return 0;
    var reqs = window.checkPasswordRequirements(password);
    var strength = 0;
    if (reqs.hasMinLength) strength += 33;
    if (reqs.hasLetter) strength += 33;
    if (reqs.hasNumber) strength += 34;
    return Math.min(100, strength);
};

window.getPasswordStrengthLevel = function(strength) {
    if (strength === 0) return { text: '', color: '', klass: '' };
    if (strength <= 33) return { text: '弱', color: '#ef4444', klass: 'bg-red-500' };
    if (strength <= 66) return { text: '中等', color: '#f59e0b', klass: 'bg-yellow-500' };
    return { text: '强', color: '#22c55e', klass: 'bg-green-500' };
};

function updateRequirementDisplay(reqId, isMet) {
    var el = document.getElementById(reqId);
    if (!el) return;
    if (isMet) {
        el.classList.remove('text-slate-400');
        el.classList.add('text-green-500');
    } else {
        el.classList.remove('text-green-500');
        el.classList.add('text-slate-400');
    }
}

window.validatePasswordInput = function() {
    var passwordInput = document.getElementById('new-password');
    if (!passwordInput) return { valid: false, error: null };
    var strengthContainer = document.getElementById('password-strength-container');
    var strengthBar = document.getElementById('password-strength-bar');
    var strengthText = document.getElementById('password-strength-text');
    var errorDiv = document.getElementById('new-password-error');
    var password = passwordInput.value;

    if (password.length === 0) {
        if (strengthContainer) strengthContainer.classList.add('hidden');
        if (errorDiv) errorDiv.classList.add('hidden');
        passwordInput.style.borderColor = '#e2e8f0';
        return { valid: false, error: null };
    }

    if (strengthContainer) strengthContainer.classList.remove('hidden');
    var reqs = window.checkPasswordRequirements(password);
    var strength = window.calculatePasswordStrength(password);
    var level = window.getPasswordStrengthLevel(strength);

    if (strengthBar) {
        strengthBar.style.width = strength + '%';
        strengthBar.className = 'h-1.5 rounded-full transition-all duration-300 ' + level.klass;
    }
    if (strengthText) {
        strengthText.textContent = level.text;
        strengthText.style.color = level.color;
    }

    updateRequirementDisplay('req-length', reqs.hasMinLength);
    updateRequirementDisplay('req-letter', reqs.hasLetter);
    updateRequirementDisplay('req-number', reqs.hasNumber);

    var allValid = reqs.hasMinLength && reqs.hasLetter && reqs.hasNumber;
    if (password.length > 0 && !allValid) {
        passwordInput.style.borderColor = '#ef4444';
        if (errorDiv) errorDiv.classList.add('hidden');
    } else if (password.length >= PASSWORD_MIN_LENGTH) {
        passwordInput.style.borderColor = '#22c55e';
        if (errorDiv) errorDiv.classList.add('hidden');
    } else {
        passwordInput.style.borderColor = '#e2e8f0';
        if (errorDiv) errorDiv.classList.add('hidden');
    }
    window.validateConfirmPassword();
    return { valid: allValid, error: null };
};

window.validateConfirmPassword = function() {
    var newPasswordInput = document.getElementById('new-password');
    var confirmPasswordInput = document.getElementById('confirm-password');
    if (!newPasswordInput || !confirmPasswordInput) return { valid: false, error: null };
    var newPassword = newPasswordInput.value;
    var confirmPassword = confirmPasswordInput.value;
    var errorDiv = document.getElementById('confirm-password-error');

    if (confirmPassword.length === 0) {
        if (errorDiv) errorDiv.classList.add('hidden');
        confirmPasswordInput.style.borderColor = '#e2e8f0';
        return { valid: false, error: null };
    }
    if (confirmPassword === newPassword && newPassword.length >= PASSWORD_MIN_LENGTH) {
        confirmPasswordInput.style.borderColor = '#22c55e';
        if (errorDiv) errorDiv.classList.add('hidden');
        return { valid: true, error: null };
    } else if (confirmPassword.length > 0) {
        confirmPasswordInput.style.borderColor = '#ef4444';
        if (errorDiv) {
            errorDiv.textContent = '两次输入的密码不一致';
            errorDiv.classList.remove('hidden');
        }
        return { valid: false, error: '两次输入的密码不一致' };
    }
    return { valid: false, error: null };
};

function showInputError(inputId, errorMessage) {
    var input = document.getElementById(inputId);
    var errorDiv = document.getElementById(inputId + '-error');
    if (input) input.style.borderColor = '#ef4444';
    if (errorDiv) {
        errorDiv.textContent = errorMessage;
        errorDiv.classList.remove('hidden');
    }
}

function clearInputError(inputId) {
    var input = document.getElementById(inputId);
    var errorDiv = document.getElementById(inputId + '-error');
    if (input) input.style.borderColor = '#e2e8f0';
    if (errorDiv) errorDiv.classList.add('hidden');
}

function clearAllPasswordErrors() {
    clearInputError('new-password');
    clearInputError('confirm-password');
    clearInputError('current-password');
}

function resetPasswordForm() {
    var newPwd = document.getElementById('new-password');
    var confirmPwd = document.getElementById('confirm-password');
    var currentPwd = document.getElementById('current-password');
    var strengthContainer = document.getElementById('password-strength-container');
    if (newPwd) newPwd.value = '';
    if (confirmPwd) confirmPwd.value = '';
    if (currentPwd) currentPwd.value = '';
    if (strengthContainer) strengthContainer.classList.add('hidden');
    clearAllPasswordErrors();
}

window.updatePassword = async function() {
    var newPasswordInput = document.getElementById('new-password');
    var confirmPasswordInput = document.getElementById('confirm-password');
    var currentPasswordInput = document.getElementById('current-password');
    var updateBtn = document.getElementById('update-password-btn');

    if (!newPasswordInput || !confirmPasswordInput || !currentPasswordInput) return;
    var newPassword = newPasswordInput.value;
    var confirmPassword = confirmPasswordInput.value;
    var currentPassword = currentPasswordInput.value;

    clearAllPasswordErrors();

    if (!currentPassword) { showInputError('current-password', '请输入当前密码'); return; }
    if (!newPassword) { showInputError('new-password', '请输入新密码'); return; }

    var reqs = window.checkPasswordRequirements(newPassword);
    if (!reqs.hasMinLength) { showInputError('new-password', '密码至少需要8个字符'); return; }
    if (!reqs.hasLetter) { showInputError('new-password', '密码必须包含字母'); return; }
    if (!reqs.hasNumber) { showInputError('new-password', '密码必须包含数字'); return; }
    if (newPassword !== confirmPassword) { showInputError('confirm-password', '两次输入的密码不一致'); return; }

    if (updateBtn) {
        updateBtn.disabled = true;
        updateBtn.textContent = '更新中...';
    }

    try {
        var response = await fetch('/api/change_password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                old_password: currentPassword,
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        });
        var result = await response.json();
        if (result.code === 0) {
            showToast('密码已更新，请重新登录', 'success');
            localStorage.removeItem('username');
            resetPasswordForm();
            setTimeout(function() { window.location.href = '/login'; }, 1500);
        } else {
            var errMsg = result.message || result.detail || '修改密码失败';
            showInputError('current-password', errMsg);
            showToast('修改密码失败: ' + errMsg, 'error');
        }
    } catch (error) {
        showInputError('current-password', '网络错误，请稍后重试');
        showToast('修改密码失败', 'error');
    } finally {
        if (updateBtn) {
            updateBtn.disabled = false;
            updateBtn.textContent = '更新密码';
        }
    }
};

// ========== Current User ==========
async function fetchCurrentUser() {
    try {
        var response = await fetch('/api/current_user', { credentials: 'include' });
        if (response.ok) {
            var data = await response.json();
            if (data.code === 0 && data.data && data.data.username) {
                var usernameEl = document.getElementById('display-username');
                if (usernameEl) usernameEl.textContent = data.data.username;
            }
        }
    } catch (error) {
        console.error('Failed to fetch current user:', error);
    }
}

// ========== Settings Load & Save ==========
var currentSettings = null;

async function fetchSettings() {
    try {
        var response = await fetch('/api/settings', { credentials: 'include' });
        if (response.ok) {
            currentSettings = await response.json();
            populateSettingsForms(currentSettings);
        }
    } catch (error) {
        console.error('Failed to fetch settings:', error);
    }
}

function populateSettingsForms(settings) {
    if (!settings) return;
    // Global Settings
    var el;
    el = document.getElementById('allow_registration'); if (el) el.checked = settings.allow_registration;
    el = document.getElementById('auto_create_home'); if (el) el.checked = settings.auto_create_home;
    el = document.getElementById('hide_login_button'); if (el) el.checked = settings.hide_login_button;
    el = document.getElementById('user_home_path'); if (el) el.value = settings.user_home_path || '/users';
    el = document.getElementById('min_password_length'); if (el) el.value = settings.min_password_length || 12;
    el = document.getElementById('forbidden_external_links'); if (el) el.checked = settings.forbidden_external_links;
    el = document.getElementById('disable_disk_space_display'); if (el) el.checked = settings.disable_disk_space_display;
    el = document.getElementById('theme'); if (el) el.value = settings.theme || '系统默认 (跟随设备)';
    el = document.getElementById('instance_name'); if (el) el.value = settings.instance_name || '';
    el = document.getElementById('branding_folder'); if (el) el.value = settings.branding_folder || '';
    el = document.getElementById('chunk_size'); if (el) el.value = settings.chunk_size || '10MB';
    el = document.getElementById('chunk_retries'); if (el) el.value = settings.chunk_retries || 5;

    // User Defaults
    if (settings.user_defaults) {
        var ud = settings.user_defaults;
        el = document.getElementById('base_path'); if (el) el.value = ud.base_path || '.';
        el = document.getElementById('language'); if (el) el.value = ud.language || 'zh-CN';
        el = document.getElementById('is_admin'); if (el) el.checked = ud.is_admin === true;
        el = document.getElementById('can_create'); if (el) el.checked = ud.can_create !== false;
        el = document.getElementById('can_delete'); if (el) el.checked = ud.can_delete !== false;
        el = document.getElementById('can_download'); if (el) el.checked = ud.can_download !== false;
        el = document.getElementById('can_edit'); if (el) el.checked = ud.can_edit !== false;
        el = document.getElementById('can_rename'); if (el) el.checked = ud.can_rename !== false;
        el = document.getElementById('can_share'); if (el) el.checked = ud.can_share !== false;
    }

    // Rules
    if (settings.rules) renderRules(settings.rules);
}

async function saveGlobalSettings() {
    if (!currentSettings) { showToast('请等待设置加载完成', 'warning'); return; }
    var updatedSettings = {
        allow_registration: document.getElementById('allow_registration').checked,
        auto_create_home: document.getElementById('auto_create_home').checked,
        hide_login_button: document.getElementById('hide_login_button').checked,
        user_home_path: document.getElementById('user_home_path').value,
        min_password_length: parseInt(document.getElementById('min_password_length').value) || 12,
        forbidden_external_links: document.getElementById('forbidden_external_links').checked,
        disable_disk_space_display: document.getElementById('disable_disk_space_display').checked,
        theme: document.getElementById('theme').value,
        instance_name: document.getElementById('instance_name').value,
        branding_folder: document.getElementById('branding_folder').value,
        chunk_size: document.getElementById('chunk_size').value,
        chunk_retries: parseInt(document.getElementById('chunk_retries').value) || 5,
        config_version: (currentSettings.config_version || 0) + 1,
        config_updated_at: new Date().toISOString(),
        user_defaults: {
            base_path: document.getElementById('base_path').value,
            language: document.getElementById('language').value,
            is_admin: document.getElementById('is_admin').checked,
            can_create: document.getElementById('can_create').checked,
            can_delete: document.getElementById('can_delete').checked,
            can_download: document.getElementById('can_download').checked,
            can_edit: document.getElementById('can_edit').checked,
            can_rename: document.getElementById('can_rename').checked,
            can_share: document.getElementById('can_share').checked
        }
    };

    try {
        var response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(updatedSettings)
        });
        if (response.ok) {
            var result = await response.json();
            currentSettings = result.settings || updatedSettings;
            showToast('全局配置已保存', 'success');
        } else {
            var err = await response.json().catch(function() { return {}; });
            showToast('保存失败: ' + (err.detail || '未知错误'), 'error');
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function saveUserDefaults() {
    if (!currentSettings) { showToast('请等待设置加载完成', 'warning'); return; }
    var updatedSettings = JSON.parse(JSON.stringify(currentSettings));
    updatedSettings.user_defaults = {
        base_path: document.getElementById('base_path').value,
        language: document.getElementById('language').value,
        is_admin: document.getElementById('is_admin').checked,
        can_create: document.getElementById('can_create').checked,
        can_delete: document.getElementById('can_delete').checked,
        can_download: document.getElementById('can_download').checked,
        can_edit: document.getElementById('can_edit').checked,
        can_rename: document.getElementById('can_rename').checked,
        can_share: document.getElementById('can_share').checked
    };

    try {
        var response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(updatedSettings)
        });
        if (response.ok) {
            var result = await response.json();
            currentSettings = result.settings || updatedSettings;
            showToast('用户默认设置已更新', 'success');
        } else {
            var err = await response.json().catch(function() { return {}; });
            showToast('保存失败: ' + (err.detail || '未知错误'), 'error');
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

window.updatePersonalSettings = function() {
    var lang = document.getElementById('personal-language').value;
    var theme = document.getElementById('personal-theme').value;
    localStorage.setItem('theme', theme);
    var goTarget = document.getElementById('personal-go-target').checked;
    localStorage.setItem('goToTargetAfterCopyMove', goTarget.toString());
    showToast('个人设置已应用', 'success');
};

// ========== Rules Management ==========
var editingRuleId = null;

function renderRules(rules) {
    var rulesList = document.getElementById('rules-list');
    if (!rulesList) return;
    if (!rules || rules.length === 0) {
        rulesList.innerHTML = '<div class="bg-slate-50 border border-slate-100 border-dashed rounded-xl p-6 text-center text-slate-500 text-sm"><i class="ri-ruler-line text-2xl text-slate-300 mb-2 block"></i>暂无全局禁止/允许规则。<br>点击右上方"新建规则"为所有用户配置访问策略。</div>';
        return;
    }
    var html = '';
    rules.forEach(function(rule) {
        html += '<div class="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-200">' +
            '<div class="flex-1">' +
                '<div class="flex items-center gap-2">' +
                    '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ' + (rule.type === 'allow' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700') + '">' + (rule.type === 'allow' ? '允许' : '禁止') + '</span>' +
                    '<span class="text-sm text-slate-700 font-mono">' + rule.path + '</span>' +
                    (rule.regex ? '<span class="text-xs text-blue-500">(正则)</span>' : '') +
                    (rule.comment ? '<span class="text-xs text-slate-400">' + rule.comment + '</span>' : '') +
                '</div>' +
            '</div>' +
            '<div class="flex items-center gap-2 ml-4">' +
                '<button class="edit-rule-btn text-blue-600 hover:text-blue-700 p-1" data-rule-id="' + rule.id + '"><i class="ri-edit-2-line"></i></button>' +
                '<button class="delete-rule-btn text-red-600 hover:text-red-700 p-1" data-rule-id="' + rule.id + '"><i class="ri-delete-bin-2-line"></i></button>' +
            '</div>' +
        '</div>';
    });
    rulesList.innerHTML = html;

    rulesList.querySelectorAll('.edit-rule-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            editRule(e.currentTarget.getAttribute('data-rule-id'), rules);
        });
    });
    rulesList.querySelectorAll('.delete-rule-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            if (confirm('确定要删除这条规则吗?')) {
                deleteRule(e.currentTarget.getAttribute('data-rule-id'));
            }
        });
    });
}

function editRule(ruleId, rules) {
    var rule = rules.find(function(r) { return String(r.id) === String(ruleId); });
    if (!rule) return;
    editingRuleId = ruleId;
    document.getElementById('rule-modal-title').textContent = '编辑规则';
    document.querySelectorAll('input[name="rule-type"]').forEach(function(radio) {
        radio.checked = radio.value === rule.type;
    });
    document.getElementById('rule-path').value = rule.path;
    document.getElementById('rule-regex').checked = rule.regex;
    document.getElementById('rule-comment').value = rule.comment || '';
    document.getElementById('rule-enabled').checked = rule.enabled !== false;
    document.getElementById('rule-modal').classList.remove('hidden');
}

async function deleteRule(ruleId) {
    try {
        var response = await fetch('/api/settings/rules/' + ruleId, {
            method: 'DELETE',
            credentials: 'include'
        });
        if (response.ok) {
            showToast('规则已删除', 'success');
            if (currentSettings && currentSettings.rules) {
                currentSettings.rules = currentSettings.rules.filter(function(r) { return String(r.id) !== String(ruleId); });
                renderRules(currentSettings.rules);
            }
        } else {
            var err = await response.json().catch(function() { return {}; });
            showToast('删除规则失败: ' + (err.detail || '未知错误'), 'error');
        }
    } catch (error) {
        showToast('删除规则失败: ' + error.message, 'error');
    }
}

// ========== User Management ==========
async function fetchUsers() {
    try {
        var response = await fetch('/api/users', { credentials: 'include' });
        if (response.ok) {
            var users = await response.json();
            updateUserTableWithUsers(users);
        }
    } catch (error) {
        console.error('Failed to fetch users:', error);
    }
}

function updateUserTableWithUsers(users) {
    var tbody = document.getElementById('user-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-8 text-center text-slate-400">暂无用户数据</td></tr>';
        return;
    }
    users.forEach(function(user) {
        var row = document.createElement('tr');
        row.innerHTML =
            '<td class="px-6 py-4 font-medium">' + user.username + '</td>' +
            '<td class="px-6 py-4">' + (user.is_admin ? '是' : '否') + '</td>' +
            '<td class="px-6 py-4">' + (user.base_path || '.') + '</td>' +
            '<td class="px-6 py-4 text-right">' +
                '<button class="user-edit-btn text-slate-400 hover:text-blue-600 p-1" data-username="' + user.username + '"><i class="ri-edit-2-line text-lg"></i></button>' +
            '</td>';
        tbody.appendChild(row);
    });

    tbody.querySelectorAll('.user-edit-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            openEditUserModal(btn.getAttribute('data-username'));
        });
    });
}

function openEditUserModal(username) {
    document.getElementById('edit-modal-title').textContent = '编辑用户 ' + username;
    document.getElementById('edit-username').value = username;
    document.getElementById('edit-password').value = '';
    document.getElementById('user-edit-modal').classList.remove('hidden');
}

// ========== Sidebar Navigation ==========
function initSidebar() {
    var links = document.querySelectorAll('.sidebar-link');
    var sections = [];
    links.forEach(function(link) {
        var href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
            var section = document.getElementById(href.substring(1));
            if (section) sections.push({ link: link, section: section });
        }
    });

    function setActiveLink(activeLink) {
        links.forEach(function(link) {
            link.classList.remove('bg-rose-50', 'text-rose-600');
            link.classList.add('text-slate-600');
            var icon = link.querySelector('i');
            if (icon) icon.classList.add('text-slate-400');
        });
        activeLink.classList.add('bg-rose-50', 'text-rose-600');
        activeLink.classList.remove('text-slate-600');
        var icon = activeLink.querySelector('i');
        if (icon) icon.classList.remove('text-slate-400');
    }

    links.forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            var href = this.getAttribute('href');
            if (!href || !href.startsWith('#')) return;
            var target = document.getElementById(href.substring(1));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                setActiveLink(this);
            }
        });
    });

    // Scroll spy
    var ticking = false;
    window.addEventListener('scroll', function() {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(function() {
            var scrollPos = window.scrollY + 120;
            var current = null;
            sections.forEach(function(item) {
                if (item.section.offsetTop <= scrollPos) {
                    current = item;
                }
            });
            if (current) setActiveLink(current.link);
            ticking = false;
        });
    });
}

// ========== Event Bindings ==========
function bindEvents() {
    // Rule modal
    var createRuleBtn = document.getElementById('create-rule-btn');
    if (createRuleBtn) {
        createRuleBtn.addEventListener('click', function() {
            editingRuleId = null;
            document.getElementById('rule-modal-title').textContent = '新建规则';
            document.querySelectorAll('input[name="rule-type"]')[0].checked = true;
            document.getElementById('rule-path').value = '';
            document.getElementById('rule-regex').checked = false;
            document.getElementById('rule-comment').value = '';
            document.getElementById('rule-enabled').checked = true;
            document.getElementById('rule-modal').classList.remove('hidden');
        });
    }

    var ruleCancelBtn = document.getElementById('rule-cancel-btn');
    if (ruleCancelBtn) {
        ruleCancelBtn.addEventListener('click', function() {
            document.getElementById('rule-modal').classList.add('hidden');
            editingRuleId = null;
        });
    }

    var ruleSaveBtn = document.getElementById('rule-save-btn');
    if (ruleSaveBtn) {
        ruleSaveBtn.addEventListener('click', async function() {
            var ruleType = document.querySelector('input[name="rule-type"]:checked').value;
            var rulePath = document.getElementById('rule-path').value.trim();
            var ruleRegex = document.getElementById('rule-regex').checked;
            var ruleComment = document.getElementById('rule-comment').value.trim();
            var ruleEnabled = document.getElementById('rule-enabled').checked;
            if (!rulePath) { showToast('请输入规则路径或正则表达式', 'warning'); return; }

            try {
                var url = editingRuleId ? '/api/settings/rules/' + editingRuleId : '/api/settings/rules';
                var method = editingRuleId ? 'PUT' : 'POST';
                var response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ type: ruleType, path: rulePath, enabled: ruleEnabled, regex: ruleRegex, comment: ruleComment })
                });
                if (response.ok) {
                    var result = await response.json();
                    showToast(editingRuleId ? '规则已更新' : '规则已创建', 'success');
                    if (!currentSettings) currentSettings = {};
                    if (!currentSettings.rules) currentSettings.rules = [];
                    if (editingRuleId) {
                        var idx = currentSettings.rules.findIndex(function(r) { return String(r.id) === String(editingRuleId); });
                        if (idx !== -1) currentSettings.rules[idx] = result.rule;
                    } else {
                        currentSettings.rules.push(result.rule);
                    }
                    renderRules(currentSettings.rules);
                    document.getElementById('rule-modal').classList.add('hidden');
                    editingRuleId = null;
                } else {
                    var err = await response.json().catch(function() { return {}; });
                    showToast('保存规则失败: ' + (err.detail || '未知错误'), 'error');
                }
            } catch (error) {
                showToast('保存规则失败: ' + error.message, 'error');
            }
        });
    }

    // Close rule modal on overlay click
    var ruleModal = document.getElementById('rule-modal');
    if (ruleModal) {
        ruleModal.addEventListener('click', function(e) {
            if (e.target === ruleModal) {
                ruleModal.classList.add('hidden');
                editingRuleId = null;
            }
        });
    }

    // New user modal
    var userNewBtn = document.getElementById('user-new-btn');
    if (userNewBtn) {
        userNewBtn.addEventListener('click', function() {
            document.getElementById('new-user-modal').classList.remove('hidden');
        });
    }

    var newCancelBtn = document.getElementById('new-cancel-btn');
    if (newCancelBtn) {
        newCancelBtn.addEventListener('click', function() {
            document.getElementById('new-user-modal').classList.add('hidden');
        });
    }

    var newSaveBtn = document.getElementById('new-save-btn');
    if (newSaveBtn) {
        newSaveBtn.addEventListener('click', async function() {
            var username = document.getElementById('new-username').value.trim();
            var password = document.getElementById('new-user-password').value;
            if (!username || !password) { showToast('请输入用户名和密码', 'warning'); return; }

            var isAdmin = document.getElementById('new-is-admin').checked;
            var basePath = document.getElementById('new-base-path').value;
            var language = document.getElementById('new-language').value;
            var forbidPwdChange = document.getElementById('new-forbid-password-change').checked;
            var permissions = {
                create: document.getElementById('new-can-create').checked,
                delete: document.getElementById('new-can-delete').checked,
                download: true,
                edit: document.getElementById('new-can-edit').checked,
                rename: document.getElementById('new-can-rename').checked,
                share: document.getElementById('new-can-share').checked
            };

            try {
                var response = await fetch('/api/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ username: username, password: password, is_admin: isAdmin, base_path: basePath, language: language, forbid_password_change: forbidPwdChange, permissions: permissions })
                });
                if (response.ok) {
                    showToast('用户已创建', 'success');
                    document.getElementById('new-user-modal').classList.add('hidden');
                    fetchUsers();
                } else {
                    var err = await response.json().catch(function() { return {}; });
                    showToast('创建用户失败: ' + (err.detail || '未知错误'), 'error');
                }
            } catch (error) {
                showToast('创建用户失败: ' + error.message, 'error');
            }
        });
    }

    // Close new user modal on overlay
    var newUserModal = document.getElementById('new-user-modal');
    if (newUserModal) {
        newUserModal.addEventListener('click', function(e) {
            if (e.target === newUserModal) newUserModal.classList.add('hidden');
        });
    }

    // Edit user modal
    var editCancelBtn = document.getElementById('edit-cancel-btn');
    if (editCancelBtn) {
        editCancelBtn.addEventListener('click', function() {
            document.getElementById('user-edit-modal').classList.add('hidden');
        });
    }

    var editSaveBtn = document.getElementById('edit-save-btn');
    if (editSaveBtn) {
        editSaveBtn.addEventListener('click', async function() {
            var username = document.getElementById('edit-username').value;
            var password = document.getElementById('edit-password').value;
            var isAdmin = document.getElementById('edit-is-admin').checked;
            var basePath = document.getElementById('edit-base-path').value;
            var language = document.getElementById('edit-language').value;
            var forbidPwdChange = document.getElementById('edit-forbid-password-change').checked;
            var permissions = {
                create: document.getElementById('edit-can-create').checked,
                delete: document.getElementById('edit-can-delete').checked,
                download: true,
                edit: document.getElementById('edit-can-edit').checked,
                rename: document.getElementById('edit-can-rename').checked,
                share: document.getElementById('edit-can-share').checked
            };
            var body = { is_admin: isAdmin, base_path: basePath, language: language, forbid_password_change: forbidPwdChange, permissions: permissions };
            if (password) body.password = password;

            try {
                var response = await fetch('/api/users/' + username, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(body)
                });
                if (response.ok) {
                    showToast('用户已更新', 'success');
                    document.getElementById('user-edit-modal').classList.add('hidden');
                    fetchUsers();
                } else {
                    var err = await response.json().catch(function() { return {}; });
                    showToast('更新用户失败: ' + (err.detail || '未知错误'), 'error');
                }
            } catch (error) {
                showToast('更新用户失败: ' + error.message, 'error');
            }
        });
    }

    var editDeleteBtn = document.getElementById('edit-delete-btn');
    if (editDeleteBtn) {
        editDeleteBtn.addEventListener('click', async function() {
            var username = document.getElementById('edit-username').value;
            if (!confirm('确定要删除用户 "' + username + '" 吗？此操作不可撤销。')) return;
            try {
                var response = await fetch('/api/users/' + username, {
                    method: 'DELETE',
                    credentials: 'include'
                });
                if (response.ok) {
                    showToast('用户已删除', 'success');
                    document.getElementById('user-edit-modal').classList.add('hidden');
                    fetchUsers();
                } else {
                    var err = await response.json().catch(function() { return {}; });
                    showToast('删除用户失败: ' + (err.detail || '未知错误'), 'error');
                }
            } catch (error) {
                showToast('删除用户失败: ' + error.message, 'error');
            }
        });
    }

    // Close edit user modal on overlay
    var userEditModal = document.getElementById('user-edit-modal');
    if (userEditModal) {
        userEditModal.addEventListener('click', function(e) {
            if (e.target === userEditModal) userEditModal.classList.add('hidden');
        });
    }

    // Global settings save
    var updateGlobalBtn = document.getElementById('update-global-settings');
    if (updateGlobalBtn) {
        updateGlobalBtn.addEventListener('click', saveGlobalSettings);
    }

    // User defaults save
    var updateUserDefaultsBtn = document.getElementById('update-user-defaults');
    if (updateUserDefaultsBtn) {
        updateUserDefaultsBtn.addEventListener('click', saveUserDefaults);
    }
}

// ========== Init ==========
async function init() {
    await fetchCurrentUser();
    await fetchSettings();
    fetchUsers();
    initSidebar();
    bindEvents();

    // Init theme from localStorage
    var savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        var darkCard = document.getElementById('theme-dark-card');
        var lightCard = document.getElementById('theme-light-card');
        if (darkCard && lightCard) {
            darkCard.classList.add('border-slate-400', 'text-white');
            darkCard.classList.remove('border-transparent');
            lightCard.classList.remove('border-rose-400', 'text-rose-500');
            lightCard.classList.add('border-transparent', 'text-slate-400');
        }
        var themeInput = document.getElementById('personal-theme');
        if (themeInput) themeInput.value = 'dark';
    }
}

document.addEventListener('DOMContentLoaded', init);
