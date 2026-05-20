const PASSWORD_MIN_LENGTH = 8;
window.togglePasswordVisibility = function(inputId) {
    const input = document.getElementById(inputId);
    const eyeIcon = document.getElementById(inputId + '-eye-icon');
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
    const hasMinLength = password.length >= PASSWORD_MIN_LENGTH;
    const hasLetter = /[a-zA-Z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    return { hasMinLength, hasLetter, hasNumber };
};
window.calculatePasswordStrength = function(password) {
    if (!password) return 0;
    const reqs = window.checkPasswordRequirements(password);
    let strength = 0;
    if (reqs.hasMinLength) strength += 33;
    if (reqs.hasLetter) strength += 33;
    if (reqs.hasNumber) strength += 34;
    return Math.min(100, strength);
};
window.getPasswordStrengthLevel = function(strength) {
    if (strength === 0) return { text: '', color: '', class: '' };
    if (strength <= 33) return { text: '弱', color: '#ef4444', class: 'bg-red-500' };
    if (strength <= 66) return { text: '中等', color: '#f59e0b', class: 'bg-yellow-500' };
    return { text: '强', color: '#22c55e', class: 'bg-green-500' };
};
window.updateRequirementDisplay = function(reqId, isMet) {
    const reqElement = document.getElementById(reqId);
    if (!reqElement) return;
    const checkMark = reqElement.querySelector('span');
    if (isMet) {
        reqElement.classList.remove('text-gray-400');
        reqElement.classList.add('text-green-500');
        checkMark.textContent = '✓';
    } else {
        reqElement.classList.remove('text-green-500');
        reqElement.classList.add('text-gray-400');
        checkMark.textContent = '✓';
    }
};
window.validatePasswordInput = function() {
    const passwordInput = document.getElementById('new-password');
    if (!passwordInput) return { valid: false, error: null };
    const strengthContainer = document.getElementById('password-strength-container');
    const strengthBar = document.getElementById('password-strength-bar');
    const strengthText = document.getElementById('password-strength-text');
    const errorDiv = document.getElementById('new-password-error');
    const password = passwordInput.value;
    if (password.length === 0) {
        if (strengthContainer) strengthContainer.classList.add('hidden');
        if (errorDiv) errorDiv.classList.add('hidden');
        passwordInput.classList.remove('border-red-500', 'border-green-500');
        passwordInput.style.borderColor = '#e5e6eb';
        return { valid: false, error: null };
    }
    if (strengthContainer) strengthContainer.classList.remove('hidden');
    const reqs = window.checkPasswordRequirements(password);
    const strength = window.calculatePasswordStrength(password);
    const level = window.getPasswordStrengthLevel(strength);
    if (strengthBar) {
        strengthBar.style.width = strength + '%';
        strengthBar.className = 'h-1.5 rounded-full transition-all duration-300 ' + level.class;
    }
    if (strengthText) {
        strengthText.textContent = level.text;
        strengthText.style.color = level.color;
    }
    window.updateRequirementDisplay('req-length', reqs.hasMinLength);
    window.updateRequirementDisplay('req-letter', reqs.hasLetter);
    window.updateRequirementDisplay('req-number', reqs.hasNumber);
    const allValid = reqs.hasMinLength && reqs.hasLetter && reqs.hasNumber;
    if (password.length > 0 && !allValid) {
        passwordInput.style.borderColor = '#ef4444';
        if (errorDiv) errorDiv.classList.add('hidden');
    } else if (password.length >= PASSWORD_MIN_LENGTH) {
        passwordInput.style.borderColor = '#22c55e';
        if (errorDiv) errorDiv.classList.add('hidden');
    } else {
        passwordInput.style.borderColor = '#e5e6eb';
        if (errorDiv) errorDiv.classList.add('hidden');
    }
    window.validateConfirmPassword();
    return { valid: allValid, error: null };
};
window.validateConfirmPassword = function() {
    const newPasswordInput = document.getElementById('new-password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    if (!newPasswordInput || !confirmPasswordInput) return { valid: false, error: null };
    const newPassword = newPasswordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    const confirmInput = document.getElementById('confirm-password');
    const errorDiv = document.getElementById('confirm-password-error');
    if (confirmPassword.length === 0) {
        if (errorDiv) errorDiv.classList.add('hidden');
        confirmInput.style.borderColor = '#e5e6eb';
        return { valid: false, error: null };
    }
    if (confirmPassword === newPassword && newPassword.length >= PASSWORD_MIN_LENGTH) {
        confirmInput.style.borderColor = '#22c55e';
        if (errorDiv) errorDiv.classList.add('hidden');
        return { valid: true, error: null };
    } else if (confirmPassword.length > 0) {
        confirmInput.style.borderColor = '#ef4444';
        if (errorDiv) {
            errorDiv.textContent = '两次输入的密码不一致';
            errorDiv.classList.remove('hidden');
        }
        return { valid: false, error: '两次输入的密码不一致' };
    }
    return { valid: false, error: null };
};
window.showInputError = function(inputId, errorMessage) {
    const input = document.getElementById(inputId);
    const errorDiv = document.getElementById(inputId + '-error');
    if (input) {
        input.style.borderColor = '#ef4444';
    }
    if (errorDiv) {
        errorDiv.textContent = errorMessage;
        errorDiv.classList.remove('hidden');
    }
};
window.clearInputError = function(inputId) {
    const input = document.getElementById(inputId);
    const errorDiv = document.getElementById(inputId + '-error');
    if (input) {
        input.style.borderColor = '#e5e6eb';
    }
    if (errorDiv) {
        errorDiv.classList.add('hidden');
    }
};
window.clearAllPasswordErrors = function() {
    window.clearInputError('new-password');
    window.clearInputError('confirm-password');
    window.clearInputError('current-password');
};
window.resetPasswordForm = function() {
    const newPasswordInput = document.getElementById('new-password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    const currentPasswordInput = document.getElementById('current-password');
    const strengthContainer = document.getElementById('password-strength-container');
    
    if (newPasswordInput) newPasswordInput.value = '';
    if (confirmPasswordInput) confirmPasswordInput.value = '';
    if (currentPasswordInput) currentPasswordInput.value = '';
    if (strengthContainer) strengthContainer.classList.add('hidden');
    window.clearAllPasswordErrors();
    if (confirmPasswordInput) confirmPasswordInput.classList.remove('border-red-500', 'border-green-500');
    if (newPasswordInput) newPasswordInput.classList.remove('border-red-500', 'border-green-500');
};
// Update password
window.updatePassword = async function() {
    const newPasswordInput = document.getElementById('new-password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    const currentPasswordInput = document.getElementById('current-password');
    const updateBtn = document.getElementById('update-password-btn');
    
    if (!newPasswordInput || !confirmPasswordInput || !currentPasswordInput) return;
    const newPassword = newPasswordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    const currentPassword = currentPasswordInput.value;
    window.clearAllPasswordErrors();
    if (!currentPassword) {
        window.showInputError('current-password', '请输入当前密码');
        return;
    }
    if (!newPassword) {
        window.showInputError('new-password', '请输入新密码');
        return;
    }
    const reqs = window.checkPasswordRequirements(newPassword);
    if (!reqs.hasMinLength) {
        window.showInputError('new-password', '密码至少需要8个字符');
        return;
    }
    if (!reqs.hasLetter) {
        window.showInputError('new-password', '密码必须包含字母');
        return;
    }
    if (!reqs.hasNumber) {
        window.showInputError('new-password', '密码必须包含数字');
        return;
    }
    if (newPassword !== confirmPassword) {
        window.showInputError('confirm-password', '两次输入的密码不一致');
        return;
    }
    if (updateBtn) {
        updateBtn.disabled = true;
        updateBtn.textContent = '更新中...';
    }
    try {
        const response = await fetch('/api/change_password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                old_password: currentPassword,
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        });
        const result = await response.json();
        if (result.code === 0) {
            alert('密码已更新，请重新登录 / Password updated successfully, please login again');
            localStorage.removeItem('username');
            window.resetPasswordForm();
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 1000);
        } else {
            var errMsg = result.message || result.detail || '修改密码失败';
            window.showInputError('current-password', errMsg);
            alert('修改密码失败: ' + errMsg + ' / Failed to change password: ' + errMsg);
        }
    } catch (error) {
        console.error('Failed to change password:', error);
        window.showInputError('current-password', '网络错误，请稍后重试');
        alert('修改密码失败 / Failed to change password');
    } finally {
        if (updateBtn) {
            updateBtn.disabled = false;
            updateBtn.textContent = '更新';
        }
    }
};
// Check authentication on load


// Test function
function testButtonClick() {
    console.log('Test button click function called');
    // 真正切换到英文
    changeLanguage('en');
    alert('Language changed to English! / 语言已切换为英文！');
}

// Fetch current user info
async function fetchCurrentUser() {
    try {
        const response = await fetch('/api/current_user', {
            credentials: 'include'
        });
        
        if (response.ok) {
            const user = await response.json();
            document.getElementById('current-user').textContent = user.username;
            // Update user table if needed
            updateUserTable(user.is_admin);
        }
    } catch (error) {
        console.error('Failed to fetch current user:', error);
        // Fallback to admin if API fails
        document.getElementById('current-user').textContent = 'admin';
        // Update user table with fallback
        updateUserTable(true);
    }
}

// Fetch users from API
async function fetchUsers() {
    try {
        const response = await fetch('/api/users', {
            credentials: 'include'
        });
        
        if (response.ok) {
            const users = await response.json();
            updateUserTableWithUsers(users);
        }
    } catch (error) {
        console.error('Failed to fetch users:', error);
    }
}

// Update user management table with users data
function updateUserTableWithUsers(users) {
    const tbody = document.querySelector('#user-management tbody');
    if (!tbody) return;
    
    // Clear existing rows
    tbody.innerHTML = '';
    
    // Add rows for each user
    users.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-6 py-4 font-medium">${user.username}</td>
            <td class="px-6 py-4">${user.is_admin ? "是" : "否"}</td>
            <td class="px-6 py-4">完成</td>
            <td class="px-6 py-4">完成</td>
            <td class="px-6 py-4 text-right">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" data-lucide="edit-3" aria-hidden="true" class="lucide lucide-edit-3 w-5 h-5 cursor-pointer hover:text-blue-600 transition-colors"><path d="M13 21h8"></path><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"></path></svg>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Update user management table
function updateUserTable(isAdmin) {
    const currentUsername = document.getElementById('current-user').textContent;
    // Fetch users from API to update the table
    fetchUsers();
}
document.addEventListener('DOMContentLoaded', () => {
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

    // Language packs
    const languagePacks = {
        'zh-CN': {
            'nav-personal': '人物',
            'nav-my-files': '我的文件',
            'nav-new-folder': '新建文件夹',
            'nav-new-file': '新建文件',
            'nav-settings': '设置',
            'nav-logout': '登出',
            'tab-personal': '个人设置',
            'tab-share': '分享管理',
            'tab-global': '全局设置',
            'tab-user': '用户管理',
            'section-files': '文件',
            'section-folders': '文件夹',
            'button-new': '新建',
            'modal-title-edit': '用户 {username}',
            'modal-title-new': '新建用户',
            'label-username': '用户名',
            'label-password': '密码',
            'label-password-hint': '（留空以避免更改）',
            'label-base-path': '目录范围',
            'label-language': '语言',
            'label-forbid-password': '禁止用户修改密码',
            'label-permissions': '权限',
            'label-admin': '管理员',
            'label-create': '创建文件和文件夹',
            'label-delete': '删除文件和文件夹',
            'label-download': '下载',
            'label-edit': '编辑',
            'label-rename': '重命名或移动文件和文件夹',
            'label-share': '分享文件',
            'button-save': '保存',
            'button-cancel': '取消',
            'button-delete': '删除',
            'permissions-hint': '你可以将该用户设置为管理员或单独选择各项权限。如果你选择了“管理员”，则其他的选项会被自动选中，同时该用户可以管理其他用户。',
            'rules-hint': '你可以为用户制定一组黑名单或白名单的规则，被屏蔽的文件将不会显示在列表中，用户也无权访问，支持正则表达式和相对于用户根目录的路径。',
            'personal-settings-title': '个人设置',
            'personal-hide-hidden': '不显示隐藏文件',
            'personal-single-click': '使用单击来打开文件和文件夹',
            'personal-go-target': '复制/移动后转到目标位置',
            'change-password-title': '更改密码',
            'change-password-new': '你的新密码',
            'change-password-confirm': '再次输入以确认你的新密码',
            'change-password-current': '您当前的密码',
            'page-home': '首页',
            'global-settings-title': '全局设置',
            'user-default-settings': '用户默认设置',
            'user-default-settings-hint': '这些是新用户的默认设置。',
            'share-management-empty': '这里没有任何文件...',
            'share-management-title': '分享管理',
            'branding-folder-path': '品牌信息文件夹路径',
            'file-browser-info': '文件浏览器',
            'chunk-upload-hint': 'File Browser 支持分块上传，在不佳的网络下也可进行高效、可靠、可续的文件上传',
            'copy-file': '复制文件',
            'move-file': '移动文件',
            'forward': '前进',
            'folder-name': '文件夹名称',
            'file-name': '文件名称',
            'allow-registration': '允许用户注册',
            'auto-create-home': '在添加新用户的同时自动创建用户的主目录',
            'hide-login-button': '从公开页面隐藏登录按钮',
            'user-home-path': '用户主目录的路径',
            'min-password-length': '最小密码长度',
            'rules': '规则',
            'rules-hint-text': '这是全局允许与禁止规则。它们作用于所有用户。你可以给每个用户定义单独的特殊规则来覆盖全局规则。',
            'branding': '品牌',
            'branding-hint': '你可以通过改变实例名称，更换 Logo，加入自定义样式，甚至禁用时 Github 的外部链接来自定义 File Browser 的外观和感觉。想获得更多信息，请查看',
            'help-docs': '帮助文档',
            'forbid-external-links': '禁止外部链接 (帮助文档除外)',
            'disable-disk-space': '禁用磁盘已用空间展示',
            'theme': '主题',
            'theme-system': '系统默认',
            'theme-light': '亮色',
            'theme-dark': '暗色',
            'apply-button': '应用',
            'button-update': '更新',
            'instance-name': '实例名称',
            'chunk-upload': '分块上传',
            'chunk-upload-size': '分块上传大小，例如 10MB 或 1GB',
            'chunk-upload-retries': '分块上传失败时的重试次数',
            'base-path': '目录范围',
            'permissions': '权限',
            'user-management-title': '用户',
            'new-button': '新建',
            'page-title': '文件管理 - Openclaw',
            'context-share': '分享',
            'context-rename': '重命名',
            'context-copy': '复制文件',
            'context-move': '移动文件',
            'context-delete': '删除',
            'context-download': '下载',
            'context-info': '信息',
            'storage-info': '存储空间',
            'storage-used': '已使用',
            'help': '帮助',
            'new-user': '新建用户',
            'edit-user': '编辑用户',
            'password-placeholder': '留空以避免更改',
            'admin': '管理员',
            'yes': '是',
            'no': '否',
            'complete': '完成'
        },
        'en': {
            'nav-personal': 'Profile',
            'nav-my-files': 'My Files',
            'nav-new-folder': 'New Folder',
            'nav-new-file': 'New File',
            'nav-settings': 'Settings',
            'nav-logout': 'Logout',
            'tab-personal': 'Personal Settings',
            'tab-share': 'Share Management',
            'tab-global': 'Global Settings',
            'tab-user': 'User Management',
            'section-files': 'Files',
            'section-folders': 'Folders',
            'button-new': 'New',
            'modal-title-edit': 'User {username}',
            'modal-title-new': 'New User',
            'label-username': 'Username',
            'label-password': 'Password',
            'label-password-hint': '(Leave blank to avoid changing)',
            'label-base-path': 'Base Path',
            'label-language': 'Language',
            'label-forbid-password': 'Forbid user to change password',
            'label-permissions': 'Permissions',
            'label-admin': 'Admin',
            'label-create': 'Create files and folders',
            'label-delete': 'Delete files and folders',
            'label-download': 'Download',
            'label-edit': 'Edit',
            'label-rename': 'Rename or move files and folders',
            'label-share': 'Share files',
            'button-save': 'Save',
            'button-cancel': 'Cancel',
            'button-delete': 'Delete',
            'permissions-hint': 'You can set this user as admin or select individual permissions. If you select "Admin", other options will be automatically selected, and this user can manage other users.',
            'rules-hint': 'You can set up a set of blacklist or whitelist rules for users. Blocked files will not be displayed in the list, and users will not have access to them. Regular expressions and paths relative to the user\'s root directory are supported.',
            'personal-settings-title': 'Personal Settings',
            'personal-hide-hidden': 'Do not show hidden files',
            'personal-single-click': 'Use single click to open files and folders',
            'personal-go-target': 'Go to target location after copy/move',
            'personal-precise-date': 'Show precise date format',
            'change-password-title': 'Change Password',
            'change-password-new': 'Your new password',
            'change-password-confirm': 'Confirm your new password',
            'change-password-current': 'Your current password',
            'page-home': 'Home',
            'global-settings-title': 'Global Settings',
            'user-default-settings': 'User Default Settings',
            'user-default-settings-hint': 'These are the default settings for new users.',
            'share-management-empty': 'There are no files here...',
            'share-management-title': 'Share Management',
            'branding-folder-path': 'Branding Folder Path',
            'file-browser-info': 'File Browser',
            'chunk-upload-hint': 'File Browser supports chunked uploads, allowing efficient, reliable, and resumable file uploads even in poor network conditions.',
            'copy-file': 'Copy File',
            'move-file': 'Move File',
            'forward': 'Forward',
            'folder-name': 'Folder Name',
            'file-name': 'File Name',
            'allow-registration': 'Allow user registration',
            'auto-create-home': 'Automatically create user home directory when adding new users',
            'hide-login-button': 'Hide login button from public page',
            'user-home-path': 'User home directory path',
            'min-password-length': 'Minimum password length',
            'rules': 'Rules',
            'rules-hint-text': 'These are global allow and deny rules. They apply to all users. You can define individual special rules for each user to override global rules.',
            'branding': 'Branding',
            'branding-hint': 'You can customize the appearance of File Browser by changing the instance name, replacing the logo, adding custom styles, and even disabling the external GitHub links. For more information, see',
            'help-docs': 'Help Documentation',
            'user-management-title': 'Users',
            'new-button': 'New',
            'page-title': 'File Manager - Openclaw',
            'context-share': 'Share',
            'context-rename': 'Rename',
            'context-copy': 'Copy',
            'context-move': 'Move',
            'context-delete': 'Delete',
            'context-download': 'Download',
            'context-info': 'Info',
            'storage-info': 'Storage',
            'storage-used': 'Used',
            'help': 'Help',
            'new-user': 'New User',
            'edit-user': 'Edit User',
            'password-placeholder': 'Leave blank to avoid changes',
            'admin': 'Admin',
            'yes': 'Yes',
            'no': 'No',
            'complete': 'Complete',
            'apply-button': 'Apply',
            'forbid-external-links': 'Forbid external links (except help documentation)',
            'disable-disk-space': 'Disable disk space display',
            'theme': 'Theme',
            'theme-system': 'System Default',
            'theme-light': 'Light',
            'theme-dark': 'Dark',
            'apply-button': 'Apply',
            'button-update': 'Update',
            'instance-name': 'Instance Name',
            'chunk-upload': 'Chunked Upload',
            'chunk-upload-size': 'Chunk upload size, e.g. 10MB or 1GB',
            'chunk-upload-retries': 'Number of retries for failed chunk uploads',
            'base-path': 'Base Path',
            'permissions': 'Permissions',
            'user-management-title': 'Users',
            'new-button': 'New'
        }
    };
    
    // Function to change language
    function changeLanguage(lang) {
        // Update navigation
        const personalNav = document.querySelector('[data-target="personal-settings-view"] span');
        if (personalNav) personalNav.textContent = languagePacks[lang]['nav-personal'];
        const myFilesNav = document.querySelector('[data-target="my-files-view"] span');
        if (myFilesNav) myFilesNav.textContent = languagePacks[lang]['nav-my-files'];
        
        // Update sidebar new folder and new file buttons
        const newFolderBtn = document.getElementById('new-folder-btn');
        if (newFolderBtn) {
            const span = newFolderBtn.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['nav-new-folder'];
        }
        const newFileBtn = document.getElementById('new-file-btn');
        if (newFileBtn) {
            const span = newFileBtn.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['nav-new-file'];
        }
        
        // Update sidebar settings button
        const settingsBtn = document.getElementById('sidebar-settings-btn');
        if (settingsBtn) {
            const span = settingsBtn.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['nav-settings'];
        }
        
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) logoutBtn.textContent = languagePacks[lang]['nav-logout'];
        
        // Update tabs
        const personalTab = document.querySelector('[data-tab="personal-settings"]');
        if (personalTab) personalTab.textContent = languagePacks[lang]['tab-personal'];
        const shareTab = document.querySelector('[data-tab="share-management"]');
        if (shareTab) shareTab.textContent = languagePacks[lang]['tab-share'];
        const globalTab = document.querySelector('[data-tab="global-settings"]');
        if (globalTab) globalTab.textContent = languagePacks[lang]['tab-global'];
        const userTab = document.querySelector('[data-tab="user-management"]');
        if (userTab) userTab.textContent = languagePacks[lang]['tab-user'];
        
        // Update sections
        const foldersSection = document.querySelector('#folders-section h2');
        if (foldersSection) foldersSection.textContent = languagePacks[lang]['section-folders'];
        const filesSection = document.querySelector('#files-section h2');
        if (filesSection) filesSection.textContent = languagePacks[lang]['section-files'];
        
        // Update buttons
        const newButton = document.querySelector('button:has(+ #user-management)');
        if (newButton) newButton.textContent = languagePacks[lang]['button-new'];
        
        // Update modals
        const editModalTitle = document.getElementById('edit-modal-title');
        if (editModalTitle) {
            const username = editModalTitle.textContent.replace('用户 ', '').replace('User ', '');
            editModalTitle.textContent = languagePacks[lang]['modal-title-edit'].replace('{username}', username);
        }
        const newModalTitle = document.querySelector('#new-user-modal h2');
        if (newModalTitle) newModalTitle.textContent = languagePacks[lang]['modal-title-new'];
        
        // Update form labels
        document.querySelectorAll('label[for="new-username"], label[for="edit-username"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-username'];
        });
        document.querySelectorAll('label[for="new-password"], label[for="edit-password"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-password'];
        });
        document.querySelectorAll('input[type="password"]').forEach(input => {
            input.placeholder = languagePacks[lang]['label-password-hint'];
        });
        document.querySelectorAll('label[for="base_path"], label[for="new-base-path"], label[for="edit-base-path"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-base-path'];
        });
        document.querySelectorAll('label[for="language"], label[for="new-language"], label[for="edit-language"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-language'];
        });
        document.querySelectorAll('label[for="new-forbid-password-change"], label[for="edit-forbid-password-change"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-forbid-password'];
        });
        document.querySelectorAll('h3').forEach(heading => {
            if (heading.textContent === '权限' || heading.textContent === 'Permissions') {
                heading.textContent = languagePacks[lang]['label-permissions'];
            }
        });
        document.querySelectorAll('label[for="new-is-admin"], label[for="edit-is-admin"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-admin'];
        });
        document.querySelectorAll('label[for="new-can-create"], label[for="edit-can-create"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-create'];
        });
        document.querySelectorAll('label[for="new-can-delete"], label[for="edit-can-delete"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-delete'];
        });
        document.querySelectorAll('label[for="new-can-download"], label[for="edit-can-download"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-download'];
        });
        document.querySelectorAll('label[for="new-can-edit"], label[for="edit-can-edit"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-edit'];
        });
        document.querySelectorAll('label[for="new-can-rename"], label[for="edit-can-rename"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-rename'];
        });
        document.querySelectorAll('label[for="new-can-share"], label[for="edit-can-share"]').forEach(label => {
            label.textContent = languagePacks[lang]['label-share'];
        });
        
        // Update buttons
        document.querySelectorAll('#new-save-btn, #edit-save-btn').forEach(button => {
            button.textContent = languagePacks[lang]['button-save'];
        });
        document.querySelectorAll('#new-cancel-btn, #edit-cancel-btn').forEach(button => {
            button.textContent = languagePacks[lang]['button-cancel'];
        });
        const deleteButton = document.getElementById('edit-delete-btn');
        if (deleteButton) deleteButton.textContent = languagePacks[lang]['button-delete'];
        
        // Update hints
        document.querySelectorAll('p').forEach(p => {
            if (p.textContent.includes('你可以将该用户设置为管理员') || p.textContent.includes('You can set this user as admin')) {
                p.textContent = languagePacks[lang]['permissions-hint'];
            } else if (p.textContent.includes('你可以为用户制定一组') || p.textContent.includes('You can set up a set of blacklist')) {
                p.textContent = languagePacks[lang]['rules-hint'];
            }
        });
        
        // Update personal settings section
        const personalSettingsCard = document.querySelector('#personal-settings .bg-white:first-child');
        if (personalSettingsCard) {
            const title = personalSettingsCard.querySelector('h2');
            if (title) title.textContent = languagePacks[lang]['personal-settings-title'];
            
            const checkboxes = personalSettingsCard.querySelectorAll('input[type="checkbox"]');
            const labels = ['personal-hide-hidden', 'personal-single-click', 'personal-go-target', 'personal-precise-date'];
            checkboxes.forEach((checkbox, index) => {
                const span = checkbox.nextElementSibling;
                if (span && labels[index]) {
                    span.textContent = languagePacks[lang][labels[index]];
                }
            });
            
            // Update theme label and options
            document.querySelectorAll('#personal-settings .bg-white:first-child label').forEach(label => {
                if (label.textContent === '主题' || label.textContent === 'Theme') {
                    label.textContent = languagePacks[lang]['theme'];
                } else if (label.textContent === '语言' || label.textContent === 'Language') {
                    label.textContent = languagePacks[lang]['label-language'];
                }
            });
            
            const themeSelect = document.getElementById('personal-theme');
            if (themeSelect) {
                const themeOptions = themeSelect.querySelectorAll('option');
                if (themeOptions.length >= 2) {
                    themeOptions[0].textContent = languagePacks[lang]['theme-light'];
                    themeOptions[1].textContent = languagePacks[lang]['theme-dark'];
                }
            }
            
            const applySettingsBtn = personalSettingsCard.querySelector('button[onclick="updatePersonalSettings()"]');
            if (applySettingsBtn) {
                applySettingsBtn.textContent = languagePacks[lang]['apply-button'];
            }
            
            // Update language options
            const personalLangSelect = document.getElementById('personal-language');
            if (personalLangSelect) {
                const langOptions = personalLangSelect.querySelectorAll('option');
                if (langOptions.length >= 2) {
                    langOptions[0].textContent = '中文 (简体)';
                    langOptions[1].textContent = 'English';
                }
            }
        }
        
        // Update change password section
        const changePasswordCard = document.querySelector('#personal-settings .bg-white:last-child');
        if (changePasswordCard) {
            const title = changePasswordCard.querySelector('h2');
            if (title) title.textContent = languagePacks[lang]['change-password-title'];
            
            const passwords = changePasswordCard.querySelectorAll('input[type="password"]');
            const placeholders = ['change-password-new', 'change-password-confirm', 'change-password-current'];
            passwords.forEach((input, index) => {
                if (input && placeholders[index]) {
                    input.placeholder = languagePacks[lang][placeholders[index]];
                }
            });
        }
        
        // Update page titles (h1)
        document.querySelectorAll('h1').forEach(h1 => {
            if (h1.textContent === '首页' || h1.textContent === 'Home') {
                h1.textContent = languagePacks[lang]['page-home'];
            }
        });
        
        // Update breadcrumbs home
        const breadcrumbHome = document.querySelector('#breadcrumbs button[data-path="root"]');
        if (breadcrumbHome) {
            const homeText = breadcrumbHome.querySelector('span');
            if (homeText) {
                homeText.textContent = languagePacks[lang]['page-home'];
            } else {
                breadcrumbHome.innerHTML = `<i data-lucide="home" class="w-4 h-4 mr-1"></i>${languagePacks[lang]['page-home']}`;
            }
        }
        
        // Update global settings title
        const globalSettingsTitle = document.querySelector('#global-settings h2');
        if (globalSettingsTitle) {
            globalSettingsTitle.textContent = languagePacks[lang]['global-settings-title'];
        }
        
        // Update user default settings title and hint
        const userDefaultSettingsTitle = document.querySelector('#user-default-settings-form h2');
        if (userDefaultSettingsTitle) {
            userDefaultSettingsTitle.textContent = languagePacks[lang]['user-default-settings'];
        }
        const userDefaultSettingsHint = document.querySelector('#user-default-settings-form p');
        if (userDefaultSettingsHint) {
            userDefaultSettingsHint.textContent = languagePacks[lang]['user-default-settings-hint'];
        }
        
        // Update share management section
        const shareManagementTitle = document.querySelector('#share-management h2');
        if (shareManagementTitle) {
            shareManagementTitle.textContent = languagePacks[lang]['share-management-title'];
        }
        const shareManagementEmpty = document.querySelector('#share-management p');
        if (shareManagementEmpty && shareManagementEmpty.textContent.includes('这里没有任何文件') || shareManagementEmpty && shareManagementEmpty.textContent.includes('There are no files')) {
            shareManagementEmpty.textContent = languagePacks[lang]['share-management-empty'];
        }
        
        // Update global settings checkboxes
        document.querySelectorAll('#global-settings-form label span').forEach(span => {
            if (span.textContent.includes('允许用户注册') || span.textContent.includes('Allow user registration')) {
                span.textContent = languagePacks[lang]['allow-registration'];
            } else if (span.textContent.includes('在添加新用户的同时自动创建') || span.textContent.includes('Automatically create user home')) {
                span.textContent = languagePacks[lang]['auto-create-home'];
            } else if (span.textContent.includes('从公开页面隐藏登录按钮') || span.textContent.includes('Hide login button from public')) {
                span.textContent = languagePacks[lang]['hide-login-button'];
            } else if (span.textContent.includes('禁止外部链接') || span.textContent.includes('Forbid external links')) {
                span.textContent = languagePacks[lang]['forbid-external-links'];
            } else if (span.textContent.includes('禁用磁盘已用空间展示') || span.textContent.includes('Disable disk space display')) {
                span.textContent = languagePacks[lang]['disable-disk-space'];
            }
        });
        
        // Update all labels in global settings form
        document.querySelectorAll('#global-settings-form label').forEach(label => {
            const text = label.textContent;
            if (text.includes('用户主目录的路径') || text.includes('User home directory path')) {
                label.textContent = languagePacks[lang]['user-home-path'];
            } else if (text.includes('最小密码长度') || text.includes('Minimum password length')) {
                label.textContent = languagePacks[lang]['min-password-length'];
            } else if (text.includes('品牌信息文件夹路径') || text.includes('Branding Folder Path')) {
                label.textContent = languagePacks[lang]['branding-folder-path'];
            } else if (text.includes('主题') || text.includes('Theme')) {
                label.textContent = languagePacks[lang]['theme'];
            } else if (text.includes('实例名称') || text.includes('Instance Name')) {
                label.textContent = languagePacks[lang]['instance-name'];
            } else if (text.includes('分块上传大小') || text.includes('Chunk upload size')) {
                label.textContent = languagePacks[lang]['chunk-upload-size'];
            } else if (text.includes('分块上传失败时的重试') || text.includes('Number of retries')) {
                label.textContent = languagePacks[lang]['chunk-upload-retries'];
            }
        });
        
        // Update user default settings labels
        document.querySelectorAll('#user-default-settings-form label').forEach(label => {
            const text = label.textContent;
            if (text.includes('目录范围') || text.includes('Base Path')) {
                label.textContent = languagePacks[lang]['base-path'];
            } else if (text === '语言' || text === 'Language') {
                label.textContent = languagePacks[lang]['label-language'];
            }
        });
        
        // Update user default settings checkboxes
        document.querySelectorAll('#user-default-settings-form label span').forEach(span => {
            if (span.textContent === '管理员' || span.textContent === 'Admin') {
                span.textContent = languagePacks[lang]['admin'];
            } else if (span.textContent.includes('创建文件和文件夹') || span.textContent.includes('Create files and folders')) {
                span.textContent = languagePacks[lang]['label-create'];
            } else if (span.textContent.includes('删除文件和文件夹') || span.textContent.includes('Delete files and folders')) {
                span.textContent = languagePacks[lang]['label-delete'];
            } else if (span.textContent === '下载' || span.textContent === 'Download') {
                span.textContent = languagePacks[lang]['label-download'];
            } else if (span.textContent === '编辑' || span.textContent === 'Edit') {
                span.textContent = languagePacks[lang]['label-edit'];
            } else if (span.textContent.includes('重命名或移动文件和文件夹') || span.textContent.includes('Rename or move files')) {
                span.textContent = languagePacks[lang]['label-rename'];
            } else if (span.textContent.includes('分享文件') || span.textContent.includes('Share files')) {
                span.textContent = languagePacks[lang]['label-share'];
            }
        });
        
        // Update permissions heading in user default settings
        document.querySelectorAll('#user-default-settings-form h3').forEach(h3 => {
            if (h3.textContent === '权限' || h3.textContent === 'Permissions') {
                h3.textContent = languagePacks[lang]['permissions'];
            }
        });
        
        // Update permissions hint in user default settings
        document.querySelectorAll('#user-default-settings-form p.text-xs').forEach(p => {
            if (p.textContent.includes('你可以将该用户设置为管理员') || p.textContent.includes('You can set this user as admin')) {
                p.textContent = languagePacks[lang]['permissions-hint'];
            }
        });
        
        // Update rules section
        document.querySelectorAll('#global-settings-form h3').forEach(h3 => {
            if (h3.textContent === '规则' || h3.textContent === 'Rules') {
                h3.textContent = languagePacks[lang]['rules'];
            }
            if (h3.textContent === '品牌' || h3.textContent === 'Branding') {
                h3.textContent = languagePacks[lang]['branding'];
            }
            if (h3.textContent === '分块上传' || h3.textContent === 'Chunked Upload') {
                h3.textContent = languagePacks[lang]['chunk-upload'];
            }
        });
        
        // Update all p tags in global settings form
        document.querySelectorAll('#global-settings-form p').forEach(p => {
            const text = p.textContent;
            if (text.includes('这是全局允许与禁止规则') || text.includes('These are global allow and deny')) {
                p.textContent = languagePacks[lang]['rules-hint-text'];
            }
            if (text.includes('你可以通过改变实例名称') || text.includes('You can customize the appearance')) {
                p.textContent = languagePacks[lang]['branding-hint'];
            }
            if (text.includes('File Browser 支持分块上传') || text.includes('File Browser supports chunked uploads')) {
                p.textContent = languagePacks[lang]['chunk-upload-hint'];
            }
        });
        
        // Update all buttons in global settings form
        document.querySelectorAll('#global-settings-form button').forEach(button => {
            const text = button.textContent.trim();
            if (text === '新建' || text === 'New') {
                button.textContent = languagePacks[lang]['new-button'];
            }
            if (text === '更新' || text === 'Update') {
                button.textContent = languagePacks[lang]['button-update'];
            }
        });
        
        // Update help docs link
        document.querySelectorAll('#global-settings-form a').forEach(a => {
            if (a.textContent.includes('帮助文档') || a.textContent.includes('Help Documentation')) {
                a.textContent = languagePacks[lang]['help-docs'];
            }
        });
        
        // Update branding checkboxes
        const forbidLinksLabel = document.querySelector('label[for="forbidden_external_links"]');
        if (forbidLinksLabel) {
            const span = forbidLinksLabel.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['forbid-external-links'];
        }
        const disableDiskLabel = document.querySelector('label[for="disable_disk_space_display"]');
        if (disableDiskLabel) {
            const span = disableDiskLabel.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['disable-disk-space'];
        }
        
        // Update theme labels
        document.querySelectorAll('#global-settings-form label').forEach(label => {
            if (label.textContent.includes('主题') || label.textContent.includes('Theme')) {
                label.textContent = languagePacks[lang]['theme'];
            }
            if (label.textContent.includes('实例名称') || label.textContent.includes('Instance Name')) {
                label.textContent = languagePacks[lang]['instance-name'];
            }
        });
        
        // Update theme options
        document.querySelectorAll('#theme option').forEach(option => {
            if (option.textContent === '系统默认' || option.textContent === 'System Default') {
                option.textContent = languagePacks[lang]['theme-system'];
            }
            if (option.textContent === '亮色' || option.textContent === 'Light') {
                option.textContent = languagePacks[lang]['theme-light'];
            }
            if (option.textContent === '暗色' || option.textContent === 'Dark') {
                option.textContent = languagePacks[lang]['theme-dark'];
            }
        });
        
        // Update chunk upload labels
        document.querySelectorAll('#global-settings-form label').forEach(label => {
            if (label.textContent.includes('分块上传大小') || label.textContent.includes('Chunk upload size')) {
                label.textContent = languagePacks[lang]['chunk-upload-size'];
            }
            if (label.textContent.includes('分块上传失败时的重试次数') || label.textContent.includes('Number of retries')) {
                label.textContent = languagePacks[lang]['chunk-upload-retries'];
            }
        });
        
        // Update user default settings section
        const basePathLabel = document.querySelector('#user-default-settings-form label[for="base_path"]');
        if (basePathLabel) {
            basePathLabel.textContent = languagePacks[lang]['base-path'];
        }
        
        // Update permissions section
        document.querySelectorAll('#user-default-settings-form h3').forEach(h3 => {
            if (h3.textContent === '权限' || h3.textContent === 'Permissions') {
                h3.textContent = languagePacks[lang]['permissions'];
            }
        });
        
        // Update user management section
        const userManagementTitle = document.querySelector('#user-management h2');
        if (userManagementTitle && (userManagementTitle.textContent === '用户' || userManagementTitle.textContent === 'Users')) {
            userManagementTitle.textContent = languagePacks[lang]['user-management-title'];
        }
        
        // Update all buttons in user management
        document.querySelectorAll('#user-management button').forEach(button => {
            if (button.textContent.trim() === '新建' || button.textContent.trim() === 'New') {
                button.textContent = languagePacks[lang]['new-button'];
            }
        });
        
        // Update user table (admin column)
        document.querySelectorAll('#user-management tbody td:nth-child(2)').forEach(td => {
            if (td.textContent === '是' || td.textContent === 'Yes') {
                td.textContent = languagePacks[lang]['yes'];
            } else if (td.textContent === '否' || td.textContent === 'No') {
                td.textContent = languagePacks[lang]['no'];
            }
        });
        
        // Update user table (status column - "完成")
        document.querySelectorAll('#user-management tbody td:nth-child(3), #user-management tbody td:nth-child(4)').forEach(td => {
            if (td.textContent === '完成' || td.textContent === 'Complete') {
                td.textContent = languagePacks[lang]['complete'];
            }
        });
        
        // Update page title
        document.title = languagePacks[lang]['page-title'];
        
        // Update context menu items
        document.querySelectorAll('.context-menu-item').forEach(item => {
            const span = item.querySelector('span');
            if (!span) return;
            
            if (span.textContent.includes('分享')) {
                span.textContent = languagePacks[lang]['context-share'];
            } else if (span.textContent.includes('重命名')) {
                span.textContent = languagePacks[lang]['context-rename'];
            } else if (span.textContent.includes('复制')) {
                span.textContent = languagePacks[lang]['context-copy'];
            } else if (span.textContent.includes('移动')) {
                span.textContent = languagePacks[lang]['context-move'];
            } else if (span.textContent === '删除') {
                span.textContent = languagePacks[lang]['context-delete'];
            } else if (span.textContent === '下载') {
                span.textContent = languagePacks[lang]['context-download'];
            } else if (span.textContent === '信息') {
                span.textContent = languagePacks[lang]['context-info'];
            }
        });
        
        // Update storage info
        const storageInfo = document.querySelector('.storage-info');
        if (storageInfo) {
            storageInfo.textContent = storageInfo.textContent.replace('存储空间', languagePacks[lang]['storage-info']).replace('Storage', languagePacks[lang]['storage-info']);
            storageInfo.textContent = storageInfo.textContent.replace('已使用', languagePacks[lang]['storage-used']).replace('Used', languagePacks[lang]['storage-used']);
        }
        
        // Update help link
        const helpLink = document.querySelector('.sidebar-footer a');
        if (helpLink && (helpLink.textContent === '帮助' || helpLink.textContent === 'Help')) {
            helpLink.textContent = languagePacks[lang]['help'];
        }
        
        // Update new user modal
        const newUserModalTitle = document.querySelector('#new-user-modal h2');
        if (newUserModalTitle && (newUserModalTitle.textContent === '新建用户' || newUserModalTitle.textContent === 'New User')) {
            newUserModalTitle.textContent = languagePacks[lang]['new-user'];
        }
        
        // Update edit user modal
        const editUserModalTitle = document.querySelector('#edit-modal-title');
        if (editUserModalTitle) {
            const username = editUserModalTitle.textContent.match(/用户 (.+)|User (.+)/);
            if (username) {
                const name = username[1] || username[2];
                editUserModalTitle.textContent = languagePacks[lang]['edit-user'] + ' ' + name;
            }
        }
        
        // Update password placeholder in edit modal
        const editPasswordInput = document.getElementById('edit-password');
        if (editPasswordInput) {
            editPasswordInput.placeholder = languagePacks[lang]['password-placeholder'];
        }
        
        // Update admin labels
        document.querySelectorAll('#user-default-settings-form label[for="is_admin"] span, #new-user-modal label[for="new-is-admin"] span, #edit-user-modal label[for="edit-is-admin"] span').forEach(span => {
            if (span.textContent === '管理员' || span.textContent === 'Admin') {
                span.textContent = languagePacks[lang]['admin'];
            }
        });
        
        // Update user management table headers
        document.querySelectorAll('#user-management th').forEach(th => {
            if (th.textContent === '用户名' || th.textContent === 'Username') {
                th.textContent = languagePacks[lang]['label-username'];
            }
            if (th.textContent === '管理员' || th.textContent === 'Admin') {
                th.textContent = languagePacks[lang]['admin'];
            }
            if (th.textContent === '目录范围' || th.textContent === 'Base Path') {
                th.textContent = languagePacks[lang]['base-path'];
            }
        });
        
        // Update update buttons text
        document.querySelectorAll('button').forEach(button => {
            if (button.textContent === '更新' || button.textContent === 'Update') {
                button.textContent = languagePacks[lang]['button-update'];
            }
        });
        
        // Update branding folder path label
        const brandingFolderLabel = document.querySelector('label[for="branding_folder"]');
        if (brandingFolderLabel) {
            brandingFolderLabel.textContent = languagePacks[lang]['branding-folder-path'];
        }
        
        // Update file browser info
        const fileBrowserInfo = document.querySelector('.sidebar-footer p');
        if (fileBrowserInfo) {
            const version = fileBrowserInfo.textContent.match(/[\d.]+/);
            if (version) {
                fileBrowserInfo.textContent = languagePacks[lang]['file-browser-info'] + ' ' + version[0];
            } else {
                fileBrowserInfo.textContent = languagePacks[lang]['file-browser-info'];
            }
        }
        
        // Update chunk upload hint
        const chunkUploadHint = document.querySelector('#global-settings .text-xs.text-gray-400');
        if (chunkUploadHint && chunkUploadHint.textContent.includes('File Browser')) {
            chunkUploadHint.textContent = languagePacks[lang]['chunk-upload-hint'];
        }
        
        // Update context menu items
        const copyFileItem = document.querySelector('[data-action="copy"]');
        if (copyFileItem) {
            const span = copyFileItem.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['copy-file'];
        }
        const moveFileItem = document.querySelector('[data-action="move"]');
        if (moveFileItem) {
            const span = moveFileItem.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['move-file'];
        }
        const forwardItem = document.querySelector('[data-action="forward"]');
        if (forwardItem) {
            const span = forwardItem.querySelector('span');
            if (span) span.textContent = languagePacks[lang]['forward'];
        }
    }
    
    // Update personal language settings
    window.updatePersonalSettings = function() {
        // Update language
        const langSelect = document.getElementById('personal-language');
        const selectedLang = langSelect.value;
        changeLanguage(selectedLang);
        
        // Update theme
        const themeSelect = document.getElementById('personal-theme');
        const selectedTheme = themeSelect.value;
        applyTheme(selectedTheme);
        localStorage.setItem('theme', selectedTheme);
        
        // Update "Go to target location after copy/move" setting
        const goTargetCheckbox = document.getElementById('personal-go-target');
        const goTarget = goTargetCheckbox.checked;
        localStorage.setItem('goToTargetAfterCopyMove', goTarget.toString());
        
        // Refresh file list
        if (typeof renderFileSystem === 'function') {
            renderFileSystem();
        }
    };
    
    // Apply theme to the page
    function applyTheme(theme) {
        const body = document.body;
        
        // Remove existing theme classes
        body.classList.remove('theme-light', 'theme-dark');
        
        // Add the selected theme class
        if (theme === 'dark') {
            body.classList.add('theme-dark');
        } else {
            body.classList.add('theme-light');
        }
        
        // Update file cards theme
        updateFileCardsTheme(theme);
    }
    
    // Update file cards theme
    function updateFileCardsTheme(theme) {
        const fileCards = document.querySelectorAll('.file-card');
        fileCards.forEach(card => {
            if (theme === 'dark') {
                card.style.backgroundColor = '#1f2937';
                card.style.borderColor = '#374151';
            } else {
                card.style.backgroundColor = '#ffffff';
                card.style.borderColor = '#e5e7eb';
            }
        });
    }
    
    // Initialize theme on page load
    function initTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            applyTheme(savedTheme);
            const themeSelect = document.getElementById('personal-theme');
            if (themeSelect) {
                themeSelect.value = savedTheme;
            }
        }
    }
    fetchCurrentUser();
    
    // User Edit Modal
    const userEditModal = document.getElementById('user-edit-modal');
    const editCancelBtn = document.getElementById('edit-cancel-btn');
    const editSaveBtn = document.getElementById('edit-save-btn');
    const editDeleteBtn = document.getElementById('edit-delete-btn');
    
    // Open edit modal when clicking edit icon
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-lucide="edit-3"]')) {
            const row = e.target.closest('tr');
            const username = row.querySelector('td:first-child').textContent;
            document.getElementById('edit-modal-title').textContent = `用户 ${username}`;
            document.getElementById('edit-username').value = username;
            userEditModal.classList.remove('hidden');
        }
    });
    
    // Close modal
    editCancelBtn.addEventListener('click', () => {
        userEditModal.classList.add('hidden');
    });
    
    // Save changes
    editSaveBtn.addEventListener('click', async () => {
        const username = document.getElementById('edit-username').value;
        const password = document.getElementById('edit-password').value;
        const isAdmin = document.getElementById('edit-is-admin').checked;
        const permissions = {
            create: document.getElementById('edit-can-create').checked,
            delete: document.getElementById('edit-can-delete').checked,
            download: true, // 下载权限默认开启且不可修改
            edit: document.getElementById('edit-can-edit').checked,
            rename: document.getElementById('edit-can-rename').checked,
            share: document.getElementById('edit-can-share').checked
        };
        
        try {
            const response = await fetch(`/api/users/${username}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({ password, is_admin: isAdmin, permissions })
            });
            
            if (response.ok) {
                const data = await response.json();
                alert('用户已更新');
                userEditModal.classList.add('hidden');
                // Refresh user table
                fetchUsers();
            } else {
                const error = await response.json();
                alert(`更新用户失败: ${error.detail}`);
            }
        } catch (error) {
            console.error('Failed to update user:', error);
            alert('更新用户失败');
        }
    });
    
    // Delete user
    editDeleteBtn.addEventListener('click', async () => {
        const username = document.getElementById('edit-username').value;
        if (confirm('确定要删除此用户吗？')) {
            try {
                const response = await fetch(`/api/users/${username}`, {
                    method: 'DELETE',
                    credentials: 'include'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    alert('用户已删除');
                    userEditModal.classList.add('hidden');
                    // Refresh user table
                    fetchUsers();
                } else {
                    const error = await response.json();
                    alert(`删除用户失败: ${error.detail}`);
                }
            } catch (error) {
                console.error('Failed to delete user:', error);
                alert('删除用户失败');
            }
        }
    });
    
    // Close modal when clicking outside
    userEditModal.addEventListener('click', (e) => {
        if (e.target === userEditModal) {
            userEditModal.classList.add('hidden');
        }
    });
    
    // New User Modal
    const newUserModal = document.getElementById('new-user-modal');
    const newCancelBtn = document.getElementById('new-cancel-btn');
    const newSaveBtn = document.getElementById('new-save-btn');
    
    // Open new user modal when clicking new button
    document.addEventListener('click', (e) => {
        if (e.target.closest('button') && e.target.closest('button').textContent.trim() === '新建' && e.target.closest('div').querySelector('h2')?.textContent === '用户') {
            newUserModal.classList.remove('hidden');
        }
    });
    
    // Close new user modal
    newCancelBtn.addEventListener('click', () => {
        newUserModal.classList.add('hidden');
    });
    
    // Save new user
    newSaveBtn.addEventListener('click', async () => {
        const username = document.getElementById('new-username').value;
        const password = document.getElementById('new-user-password').value;
        if (!username || !password) {
            alert('请输入用户名和密码');
            return;
        }
        
        const isAdmin = document.getElementById('new-is-admin').checked;
        const permissions = {
            create: document.getElementById('new-can-create').checked,
            delete: document.getElementById('new-can-delete').checked,
            download: true, // 下载权限默认开启且不可修改
            edit: document.getElementById('new-can-edit').checked,
            rename: document.getElementById('new-can-rename').checked,
            share: document.getElementById('new-can-share').checked
        };
        
        try {
            const response = await fetch('/api/users', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({ username, password, is_admin: isAdmin, permissions })
            });
            
            if (response.ok) {
                const data = await response.json();
                alert('用户已创建');
                newUserModal.classList.add('hidden');
                // Refresh user table
                fetchUsers();
            } else {
                const error = await response.json();
                alert(`创建用户失败: ${error.detail}`);
            }
        } catch (error) {
            console.error('Failed to create user:', error);
            alert('创建用户失败');
        }
    });
    
    // Close new user modal when clicking outside
    newUserModal.addEventListener('click', (e) => {
        if (e.target === newUserModal) {
            newUserModal.classList.add('hidden');
        }
    });
    
    // --- Elements ---
    const contextMenu = document.getElementById('context-menu');
    const defaultHeaderActions = document.getElementById('default-header-actions');
    const selectedHeaderActions = document.getElementById('selected-header-actions');
    const editorView = document.getElementById('editor-view');
    const editorFilename = document.getElementById('editor-filename');
    const breadcrumbFilename = document.getElementById('breadcrumb-filename');
    const fileList = document.getElementById('file-list');
    const folderList = document.getElementById('folder-list');
    const foldersSection = document.getElementById('folders-section');
    const filesSection = document.getElementById('files-section');
    const emptyState = document.getElementById('empty-state');
    const breadcrumbs = document.getElementById('breadcrumbs');
     const logoutBtn = document.getElementById('logout-btn');
     // --- Settings Logic ---
     let currentSettings = null;
     const fetchSettings = async () => {
         try {
             const response = await fetch('/api/settings');
             if (response.ok) {
                 currentSettings = await response.json();
                 populateSettingsForms(currentSettings);
             }
         } catch (error) {
             console.error('Failed to fetch settings:', error);
         }
     };
     const populateSettingsForms = (settings) => {
         // Global Settings
         document.getElementById('allow_registration').checked = settings.allow_registration;
         document.getElementById('auto_create_home').checked = settings.auto_create_home;
         document.getElementById('hide_login_button').checked = settings.hide_login_button;
         document.getElementById('user_home_path').value = settings.user_home_path;
         document.getElementById('min_password_length').value = settings.min_password_length;
         document.getElementById('forbidden_external_links').checked = settings.forbidden_external_links;
         document.getElementById('disable_disk_space_display').checked = settings.disable_disk_space_display;
         document.getElementById('theme').value = settings.theme;
         document.getElementById('instance_name').value = settings.instance_name;
         document.getElementById('branding_folder').value = settings.branding_folder;
         document.getElementById('chunk_size').value = settings.chunk_size;
         document.getElementById('chunk_retries').value = settings.chunk_retries;
         // Config version display
         const versionEl = document.getElementById('config-version-display');
         const updatedEl = document.getElementById('config-updated-display');
         if (versionEl) versionEl.textContent = `v${settings.config_version || 0}`;
         if (updatedEl) updatedEl.textContent = settings.config_updated_at
             ? new Date(settings.config_updated_at).toLocaleString('zh-CN')
             : '-';
         // Rules
         if (settings.rules) {
             renderRules(settings.rules);
         }
         // User Default Settings
         document.getElementById('base_path').value = settings.user_defaults.base_path;
         document.getElementById('language').value = settings.user_defaults.language;
         document.getElementById('is_admin').checked = settings.user_defaults.is_admin;
         document.getElementById('can_create').checked = settings.user_defaults.can_create;
         document.getElementById('can_delete').checked = settings.user_defaults.can_delete;
         document.getElementById('can_download').checked = settings.user_defaults.can_download;
         document.getElementById('can_edit').checked = settings.user_defaults.can_edit;
         document.getElementById('can_rename').checked = settings.user_defaults.can_rename;
         document.getElementById('can_share').checked = settings.user_defaults.can_share;
         loadMemoryUsage(settings.disable_disk_space_display);
     };
     const formatMemorySize = (bytes) => {
         if (bytes >= 1024 * 1024 * 1024) {
             return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
         } else if (bytes >= 1024 * 1024) {
             return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
         } else {
             return (bytes / 1024).toFixed(0) + ' KB';
         }
     };
     let memoryMonitorInterval = null;
     const loadMemoryUsage = (disabled = false) => {
         const container = document.getElementById('storage-info-container');
         const usageText = document.getElementById('memory-usage-text');
         const usageBar = document.getElementById('memory-usage-bar');
         if (!container || !usageText || !usageBar) return;
         if (disabled) {
             container.style.display = 'none';
             if (memoryMonitorInterval) {
                 clearInterval(memoryMonitorInterval);
                 memoryMonitorInterval = null;
             }
             return;
         }
         container.style.display = 'block';
         const memInfo = performance.memory;
         if (memInfo && memInfo.usedJSHeapSize !== undefined && memInfo.jsHeapSizeLimit !== undefined) {
             const usedHeap = memInfo.usedJSHeapSize;
             const totalLimit = memInfo.jsHeapSizeLimit;
             const percent = Math.min((usedHeap / totalLimit) * 100, 100);
             const usedFormatted = formatMemorySize(usedHeap);
             const totalFormatted = formatMemorySize(totalLimit);
             let deviceInfo = '';
             if (navigator.deviceMemory) {
                 deviceInfo = ` | 设备 ${navigator.deviceMemory} GB`;
             }
             usageText.textContent = `${usedFormatted} / ${totalFormatted}${deviceInfo}`;
             usageBar.style.width = `${percent}%`;
         } else if (navigator.deviceMemory) {
             usageText.textContent = `设备内存: ${navigator.deviceMemory} GB`;
             usageBar.style.width = '0%';
         } else {
             usageText.textContent = '浏览器不支持内存信息';
             usageBar.style.width = '0%';
         }
         if (!memoryMonitorInterval) {
             memoryMonitorInterval = setInterval(() => loadMemoryUsage(false), 2000);
         }
     };
     const saveAllSettings = async () => {
         if (!currentSettings) return;
         // Gather Global Settings
         const updatedSettings = {
             ...currentSettings,
             allow_registration: document.getElementById('allow_registration').checked,
             auto_create_home: document.getElementById('auto_create_home').checked,
             hide_login_button: document.getElementById('hide_login_button').checked,
             user_home_path: document.getElementById('user_home_path').value,
             min_password_length: parseInt(document.getElementById('min_password_length').value),
             forbidden_external_links: document.getElementById('forbidden_external_links').checked,
             disable_disk_space_display: document.getElementById('disable_disk_space_display').checked,
             theme: document.getElementById('theme').value,
             instance_name: document.getElementById('instance_name').value,
             branding_folder: document.getElementById('branding_folder').value,
             chunk_size: document.getElementById('chunk_size').value,
             chunk_retries: parseInt(document.getElementById('chunk_retries').value),
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
             const response = await fetch('/api/settings', {
                 method: 'POST',
                 headers: { 
                     'Content-Type': 'application/json'
                 },
                 credentials: 'include',
                 body: JSON.stringify(updatedSettings)
             });
             if (response.ok) {
                 const result = await response.json();
                 if (result.settings) {
                     currentSettings = result.settings;
                 } else {
                     currentSettings = updatedSettings;
                 }
                 alert('Settings updated successfully / 设置已更新');
                 // Apply language change after saving
                 const selectedLang = document.getElementById('language').value;
                 changeLanguage(selectedLang);
             } else {
                 const errorData = await response.json().catch(() => ({}));
                 alert('Failed to save settings: ' + (errorData.detail || 'Unknown error'));
             }
         } catch (error) {
             console.error('Failed to save settings:', error);
             alert('Failed to save settings: ' + error.message);
         }
     };
     document.getElementById('update-global-settings').addEventListener('click', () => {
         console.log('Global settings update button clicked');
         saveGlobalSettings();
     });
     document.getElementById('update-user-defaults').addEventListener('click', () => {
         console.log('User defaults update button clicked');
         saveUserDefaults();
     });
     const saveGlobalSettings = async () => {
         if (!currentSettings) return;
         const updatedSettings = {
             ...currentSettings,
             allow_registration: document.getElementById('allow_registration').checked,
             auto_create_home: document.getElementById('auto_create_home').checked,
             hide_login_button: document.getElementById('hide_login_button').checked,
             user_home_path: document.getElementById('user_home_path').value,
             min_password_length: parseInt(document.getElementById('min_password_length').value),
             forbidden_external_links: document.getElementById('forbidden_external_links').checked,
             disable_disk_space_display: document.getElementById('disable_disk_space_display').checked,
             theme: document.getElementById('theme').value,
             instance_name: document.getElementById('instance_name').value,
             branding_folder: document.getElementById('branding_folder').value,
             chunk_size: document.getElementById('chunk_size').value,
             chunk_retries: parseInt(document.getElementById('chunk_retries').value)
         };
         try {
             const response = await fetch('/api/settings', {
                 method: 'POST',
                 headers: {
                     'Content-Type': 'application/json'
                 },
                 credentials: 'include',
                 body: JSON.stringify(updatedSettings)
             });
             if (response.ok) {
                 const result = await response.json();
                 if (result.settings) {
                     currentSettings = result.settings;
                 } else {
                     currentSettings = updatedSettings;
                 }
                 alert('全局设置已更新');
                 loadMemoryUsage(currentSettings.disable_disk_space_display);
                 refreshConfigInfo();
             } else {
                 const errorData = await response.json().catch(() => ({}));
                 alert('保存全局设置失败: ' + (errorData.detail || '未知错误'));
             }
         } catch (error) {
             console.error('Failed to save global settings:', error);
             alert('保存全局设置失败: ' + error.message);
         }
     };
     const saveUserDefaults = async () => {
         if (!currentSettings) return;
         const updatedSettings = {
             ...currentSettings,
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
             const response = await fetch('/api/settings', {
                 method: 'POST',
                 headers: {
                     'Content-Type': 'application/json'
                 },
                 credentials: 'include',
                 body: JSON.stringify(updatedSettings)
             });
             if (response.ok) {
                 const result = await response.json();
                 if (result.settings) {
                     currentSettings = result.settings;
                 } else {
                     currentSettings = updatedSettings;
                 }
                 alert('用户默认设置已更新');
                 // Apply language change after saving
                 const selectedLang = document.getElementById('language').value;
                 changeLanguage(selectedLang);
             } else {
                 const errorData = await response.json().catch(() => ({}));
                 alert('保存用户默认设置失败: ' + (errorData.detail || '未知错误'));
             }
         } catch (error) {
             console.error('Failed to save user defaults:', error);
             alert('保存用户默认设置失败: ' + error.message);
         }
     };
     // --- Configuration Management ---
     const refreshConfigInfo = () => {
         if (!currentSettings) return;
         const versionEl = document.getElementById('config-version-display');
         const updatedEl = document.getElementById('config-updated-display');
         if (versionEl) versionEl.textContent = `v${currentSettings.config_version || 0}`;
         if (updatedEl) updatedEl.textContent = currentSettings.config_updated_at
             ? new Date(currentSettings.config_updated_at).toLocaleString('zh-CN')
             : '-';
     };
     fetchSettings();
     // --- Rules Management Logic ---
     let editingRuleId = null;
     const renderRules = (rules) => {
         const rulesList = document.getElementById('rules-list');
         if (!rulesList) return;
         if (!rules || rules.length === 0) {
             rulesList.innerHTML = '<p class="text-xs text-gray-400">暂无规则</p>';
             return;
         }
         rulesList.innerHTML = rules.map(rule => `
             <div class="flex items-center justify-between p-2 bg-gray-50 rounded-md border border-gray-200">
                 <div class="flex-1">
                     <div class="flex items-center space-x-2">
                         <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${rule.type === 'allow' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                             ${rule.type === 'allow' ? '允许' : '禁止'}
                         </span>
                         <span class="text-sm text-gray-700 font-mono">${rule.path}</span>
                         ${rule.regex ? '<span class="text-xs text-blue-500">(正则)</span>' : ''}
                         ${rule.comment ? `<span class="text-xs text-gray-400">${rule.comment}</span>` : ''}
                     </div>
                 </div>
                 <div class="flex items-center space-x-2 ml-4">
                     <button class="edit-rule-btn text-blue-600 hover:text-blue-700" data-rule-id="${rule.id}">
                         <i data-lucide="edit-2" class="w-4 h-4"></i>
                     </button>
                     <button class="delete-rule-btn text-red-600 hover:text-red-700" data-rule-id="${rule.id}">
                         <i data-lucide="trash-2" class="w-4 h-4"></i>
                     </button>
                 </div>
             </div>
         `).join('');
         // Re-initialize Lucide icons
         if (window.lucide) {
             window.lucide.createIcons();
         }
         // Add event listeners
         rulesList.querySelectorAll('.edit-rule-btn').forEach(btn => {
             btn.addEventListener('click', (e) => {
                 const ruleId = e.currentTarget.getAttribute('data-rule-id');
                 editRule(ruleId, rules);
             });
         });
         rulesList.querySelectorAll('.delete-rule-btn').forEach(btn => {
             btn.addEventListener('click', async (e) => {
                 const ruleId = e.currentTarget.getAttribute('data-rule-id');
                 if (confirm('确定要删除这条规则吗?')) {
                     await deleteRule(ruleId);
                 }
             });
         });
     };
     const editRule = (ruleId, rules) => {
         const rule = rules.find(r => r.id === ruleId);
         if (!rule) return;
         editingRuleId = ruleId;
         const modal = document.getElementById('rule-modal');
         const modalTitle = document.getElementById('rule-modal-title');
         modalTitle.textContent = '编辑规则';
         document.querySelectorAll('input[name="rule-type"]').forEach(radio => {
             radio.checked = radio.value === rule.type;
         });
         document.getElementById('rule-path').value = rule.path;
         document.getElementById('rule-regex').checked = rule.regex;
         document.getElementById('rule-comment').value = rule.comment || '';
         document.getElementById('rule-enabled').checked = rule.enabled;
         modal.classList.remove('hidden');
     };
     const deleteRule = async (ruleId) => {
         try {
             const response = await fetch(`/api/settings/rules/${ruleId}`, {
                 method: 'DELETE',
                 credentials: 'include'
             });
             if (response.ok) {
                 alert('规则已删除');
                 if (currentSettings) {
                     currentSettings.rules = currentSettings.rules.filter(r => r.id !== ruleId);
                     renderRules(currentSettings.rules);
                 }
             } else {
                 const errorData = await response.json().catch(() => ({}));
                 alert('删除规则失败: ' + (errorData.detail || '未知错误'));
             }
         } catch (error) {
             console.error('Delete rule error:', error);
             alert('删除规则失败: ' + error.message);
         }
     };
     // Open rule modal
     document.getElementById('create-rule-btn').addEventListener('click', () => {
         editingRuleId = null;
         const modal = document.getElementById('rule-modal');
         const modalTitle = document.getElementById('rule-modal-title');
         modalTitle.textContent = '新建规则';
         document.querySelectorAll('input[name="rule-type"]')[0].checked = true;
         document.getElementById('rule-path').value = '';
         document.getElementById('rule-regex').checked = false;
         document.getElementById('rule-comment').value = '';
         document.getElementById('rule-enabled').checked = true;
         modal.classList.remove('hidden');
     });
     // Cancel rule modal
     document.getElementById('rule-cancel-btn').addEventListener('click', () => {
         document.getElementById('rule-modal').classList.add('hidden');
         editingRuleId = null;
     });
     // Save rule
     document.getElementById('rule-save-btn').addEventListener('click', async () => {
         const ruleType = document.querySelector('input[name="rule-type"]:checked').value;
         const rulePath = document.getElementById('rule-path').value.trim();
         const ruleRegex = document.getElementById('rule-regex').checked;
         const ruleComment = document.getElementById('rule-comment').value.trim();
         const ruleEnabled = document.getElementById('rule-enabled').checked;
         if (!rulePath) {
             alert('请输入规则路径或正则表达式');
             return;
         }
         try {
             const url = editingRuleId
                 ? `/api/settings/rules/${editingRuleId}`
                 : '/api/settings/rules';
             const method = editingRuleId ? 'PUT' : 'POST';
             const response = await fetch(url, {
                 method,
                 headers: {
                     'Content-Type': 'application/json'
                 },
                 credentials: 'include',
                 body: JSON.stringify({
                     type: ruleType,
                     path: rulePath,
                     enabled: ruleEnabled,
                     regex: ruleRegex,
                     comment: ruleComment
                 })
             });
             if (response.ok) {
                 const result = await response.json();
                 alert(editingRuleId ? '规则已更新' : '规则已创建');
                 if (currentSettings) {
                     if (editingRuleId) {
                         const index = currentSettings.rules.findIndex(r => r.id === editingRuleId);
                         if (index !== -1) {
                             currentSettings.rules[index] = result.rule;
                         }
                     } else {
                         currentSettings.rules.push(result.rule);
                     }
                     renderRules(currentSettings.rules);
                 }
                 document.getElementById('rule-modal').classList.add('hidden');
                 editingRuleId = null;
             } else {
                 const errorData = await response.json().catch(() => ({}));
                 alert('保存规则失败: ' + (errorData.detail || '未知错误'));
             }
         } catch (error) {
             console.error('Save rule error:', error);
             alert('保存规则失败: ' + error.message);
         }
     });
     // Close modal on overlay click
     document.getElementById('rule-modal').addEventListener('click', (e) => {
         if (e.target.id === 'rule-modal') {
             document.getElementById('rule-modal').classList.add('hidden');
             editingRuleId = null;
         }
     });
     // --- Logout Logic ---
    logoutBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        try {
            await fetch('/api/logout', {
                method: 'POST',
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout API call failed:', error);
        }
        localStorage.removeItem('file_manager_expires_at');
        window.location.href = '/';
    });
    let selectedFileCard = null;
    let editorInstance = null;
    let currentPath = []; // Array of folder names
    let currentEditingItem = null; // Currently open file item
    
    // --- Path Persistence Functions ---
    const saveCurrentPath = () => {
        // Save current path to localStorage
        localStorage.setItem('lastVisitedPath', JSON.stringify(currentPath));
    };
    
    const loadSavedPath = () => {
        // Load saved path from localStorage
        const savedPath = localStorage.getItem('lastVisitedPath');
        if (savedPath) {
            try {
                const parsedPath = JSON.parse(savedPath);
                if (Array.isArray(parsedPath)) {
                    return parsedPath;
                }
            } catch (e) {
                console.error('Error loading saved path:', e);
            }
        }
        return [];
    };
    // --- Utilities ---
    const saveFile = async () => {
        if (!currentEditingItem) return;
        const newContent = editorInstance.getValue();
        const result = await fileOps.saveFile(
            currentEditingItem.path, newContent, currentEditingItem.name
        );
        if (result) {
            currentEditingItem.content = newContent;
            currentEditingItem.originalContent = newContent;
            // Hide modified indicator
            const indicator = document.getElementById('editor-modified-indicator');
            if (indicator) indicator.classList.add('hidden');
            renderFileSystem();
        }
    };
    const formatBytes = (bytes, decimals = 2) => {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    };
    const formatTimeAgo = (date) => {
        const now = new Date();
        const diffInSeconds = Math.floor((now - new Date(date)) / 1000);
        
        if (diffInSeconds < 60) return '刚刚';
        
        const diffInMinutes = Math.floor(diffInSeconds / 60);
        if (diffInMinutes < 60) return `${diffInMinutes} 分钟前`;
        
        const diffInHours = Math.floor(diffInMinutes / 60);
        if (diffInHours < 24) return `${diffInHours} 小时前`;
        
        const diffInDays = Math.floor(diffInHours / 24);
        if (diffInDays < 30) return `${diffInDays} 天前`;
        
        const diffInMonths = Math.floor(diffInDays / 30);
        if (diffInMonths < 12) return `${diffInMonths} 个月前`;
        
        return `${Math.floor(diffInMonths / 12)} 年前`;
    };
    // --- File System Helpers (Linux Remote File System via SSH) ---
    const getFullPath = () => {
        return currentPath.length === 0 ? '/' : '/' + currentPath.join('/');
    };
    async function fetchDirectory(dirPath) {
        try {
            const response = await fetch(`/api/files?path=${encodeURIComponent(dirPath)}`);
            return await response.json();
        } catch (e) {
            console.error('Fetch directory error:', e);
            return { success: false, items: [], error: e.message };
        }
    }
    function formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + units[i];
    }
    function formatModificationDate(isoStr) {
        const d = new Date(isoStr);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}`;
    }
    function getFileTypeDesc(name, type) {
        if (type === 'folder') return '文件夹';
        const ext = name.split('.').pop().toLowerCase();
        const typeMap = {
            'txt': '文本文件', 'py': 'Python 文件', 'js': 'JavaScript 文件',
            'ts': 'TypeScript 文件', 'json': 'JSON 文件', 'html': 'HTML 文件',
            'css': 'CSS 文件', 'xml': 'XML 文件', 'md': 'Markdown 文件',
            'pdf': 'PDF 文件', 'doc': 'Word 文档', 'docx': 'Word 文档',
            'xls': 'Excel 表格', 'xlsx': 'Excel 表格', 'ppt': 'PPT 文件',
            'pptx': 'PPT 文件', 'jpg': 'JPEG 图片', 'jpeg': 'JPEG 图片',
            'png': 'PNG 图片', 'gif': 'GIF 图片', 'bmp': 'BMP 图片',
            'svg': 'SVG 图片', 'webp': 'WebP 图片', 'ico': '图标文件',
            'zip': 'ZIP 压缩包', 'rar': 'RAR 压缩包', '7z': '7z 压缩包',
            'gz': 'GZ 压缩包', 'tar': 'TAR 归档', 'exe': '可执行文件',
            'dll': 'DLL 文件', 'msi': '安装包', 'log': '日志文件',
            'cfg': '配置文件', 'ini': '配置文件', 'sql': 'SQL 文件',
            'bat': '批处理文件', 'ps1': 'PowerShell 文件', 'sh': 'Shell 脚本',
            'mp3': '音频文件', 'mp4': '视频文件', 'avi': '视频文件',
            'mkv': '视频文件', 'wav': '音频文件', 'flac': '音频文件',
            'cpp': 'C++ 文件', 'c': 'C 文件', 'h': '头文件', 'java': 'Java 文件',
            'go': 'Go 文件', 'rs': 'Rust 文件', 'php': 'PHP 文件',
            'rb': 'Ruby 文件', 'yaml': 'YAML 文件', 'yml': 'YAML 文件',
            'toml': 'TOML 文件', 'csv': 'CSV 文件', 'tmp': '临时文件',
            'lnk': '快捷方式', 'url': 'URL 快捷方式'
        };
        return typeMap[ext] || `${ext.toUpperCase()} 文件`;
    }
    function getFileIcon(name, type) {
        if (type === 'folder') return 'folder';
        const ext = name.split('.').pop().toLowerCase();
        const iconMap = {
            'txt': 'file-text', 'py': 'code-2', 'js': 'file-json',
            'ts': 'file-code', 'json': 'code', 'html': 'file-code',
            'css': 'file-code', 'md': 'file-text', 'pdf': 'file',
            'doc': 'file', 'docx': 'file', 'xls': 'file-spreadsheet',
            'xlsx': 'file-spreadsheet', 'jpg': 'image', 'jpeg': 'image',
            'png': 'image', 'gif': 'image', 'bmp': 'image', 'svg': 'image',
            'webp': 'image', 'ico': 'image', 'zip': 'archive', 'rar': 'archive',
            'exe': 'terminal', 'dll': 'box', 'log': 'file-text',
            'cfg': 'settings', 'ini': 'settings', 'sql': 'database',
            'bat': 'terminal', 'ps1': 'terminal', 'sh': 'terminal',
            'mp3': 'music', 'mp4': 'video', 'avi': 'video', 'mkv': 'video',
            'cpp': 'file-code', 'java': 'file-code', 'go': 'file-code',
            'rs': 'file-code', 'php': 'file-code', 'yaml': 'file-code',
            'yml': 'file-code', 'csv': 'file-text', 'lnk': 'external-link'
        };
        return iconMap[ext] || 'file';
    }
    function getFileIconColor(name, type) {
        if (type === 'folder') return '';
        const ext = name.split('.').pop().toLowerCase();
        const codeExts = ['py', 'js', 'ts', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'toml', 'sql', 'cpp', 'c', 'h', 'java', 'go', 'rs', 'php', 'rb', 'sh', 'bat', 'ps1'];
        const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico'];
        const archiveExts = ['zip', 'rar', '7z', 'gz', 'tar'];
        const docExts = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'md', 'txt', 'csv'];
        if (codeExts.includes(ext)) return 'text-blue-500';
        if (imageExts.includes(ext)) return 'text-green-500';
        if (archiveExts.includes(ext)) return 'text-yellow-500';
        if (docExts.includes(ext)) return 'text-purple-500';
        return 'text-gray-400';
    }
    // --- Remote File API Operations ---
    async function loadChildItems(dirPath, container) {
        const data = await fetchDirectory(dirPath);
        if (!data.success || !data.items) return;
        const hideHidden = document.getElementById('personal-hide-hidden')?.checked || false;
        data.items.forEach(item => {
            if (hideHidden && item.name.startsWith('.')) return;
            const childRow = document.createElement('div');
            childRow.className = 'flex items-center py-2 px-3 hover:bg-gray-50 rounded cursor-pointer';
            const iconName = getFileIcon(item.name, item.type);
            const typeDesc = getFileTypeDesc(item.name, item.type);
            childRow.innerHTML = `
                <i data-lucide="${iconName}" class="w-4 h-4 mr-2 flex-shrink-0 ${item.type === 'folder' ? '' : getFileIconColor(item.name, item.type)}"></i>
                <span class="text-sm truncate flex-1">${item.name}</span>
                <span class="text-xs text-gray-400 mx-2 w-16 text-right flex-shrink-0">${item.type === 'file' ? formatFileSize(item.size) : '文件夹'}</span>
                <span class="text-xs text-gray-400 flex-shrink-0">${formatModificationDate(item.modified)}</span>
            `;
            if (item.type === 'folder') {
                childRow.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const basePath = dirPath.replace(/\/$/, '');
                    currentPath = basePath.replace('/', '').split('/').filter(p => p);
                    currentPath.push(item.name);
                    saveCurrentPath();
                    renderFileSystem();
                });
            }
            container.appendChild(childRow);
        });
        lucide.createIcons();
    }
    const renderFileSystem = async () => {
        try {
            folderList.innerHTML = '';
            fileList.innerHTML = '';
            const dirPath = getFullPath();
            showLoading();
            console.log('[文件系统] renderFileSystem - 请求路径:', dirPath);
            const data = await fetchDirectory(dirPath);
            if (!data.success) {
                hideLoading();
                console.warn('[文件系统] API 返回失败:', data.error);
                if (data.error && data.error.indexOf('SSH') !== -1) {
                    showToast('SSH 连接问题: ' + data.error + '. 请检查侧边栏连接状态', 'error', 5000);
                }
                if (currentPath.length > 0) {
                    currentPath = [];
                    saveCurrentPath();
                    return renderFileSystem();
                }
                lucide.createIcons();
                updateEmptyState();
                return;
            }
            hideLoading();
            if (data.items && data.items.length > 0) {
                console.log('[文件系统] 加载成功:', dirPath, data.items.length, '项');
            } else {
                console.log('[文件系统] 目录为空:', dirPath);
            }
            // Update Breadcrumbs
            breadcrumbs.innerHTML = `
                <button class="hover:text-blue-600 flex items-center" data-path="root">
                    <i data-lucide="home" class="w-4 h-4 mr-1"></i>
                    首页
                </button>
            `;
            let pathAcc = [];
            currentPath.forEach((segment) => {
                pathAcc.push(segment);
                const pathStr = pathAcc.join('/');
                breadcrumbs.innerHTML += `
                    <i data-lucide="chevron-right" class="w-4 h-4 text-gray-400"></i>
                    <button class="hover:text-blue-600" data-path="${pathStr}">${segment}</button>
                `;
            });
            // Bind Breadcrumb Clicks
            breadcrumbs.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    const path = btn.dataset.path;
                    if (path === 'root') {
                        currentPath = [];
                    } else {
                        currentPath = path.split('/');
                    }
                    saveCurrentPath();
                    renderFileSystem();
                });
            });
            // Check hide hidden files setting
            const hideHidden = document.getElementById('personal-hide-hidden')?.checked || false;
            if (!data.items || data.items.length === 0) {
                lucide.createIcons();
                updateEmptyState();
                return;
            }
            const folders = data.items.filter(item => item.type === 'folder' && !(hideHidden && item.name.startsWith('.')));
            const files = data.items.filter(item => item.type === 'file' && !(hideHidden && item.name.startsWith('.')));
            folders.forEach(item => {
                const card = document.createElement('div');
                card.className = 'file-card folder-card bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer flex items-center';
                card.innerHTML = `
                    <div class="w-12 h-12 flex items-center justify-center mr-4">
                        <i data-lucide="folder" class="w-8 h-8"></i>
                    </div>
                    <div class="min-w-0 flex-1">
                        <p class="text-sm font-medium truncate">${item.name}</p>
                        <p class="text-[10px] text-gray-400">文件夹</p>
                        <p class="text-[10px] text-gray-400">修改日期: ${formatModificationDate(item.modified)}</p>
                    </div>
                    <button class="expand-toggle ml-2 p-1.5 hover:bg-black/5 rounded transition-colors" title="展开">
                        <i data-lucide="chevron-right" class="w-4 h-4 text-gray-500"></i>
                    </button>
                `;
                const expandContainer = document.createElement('div');
                expandContainer.className = 'hidden border-l-2 border-gray-200 ml-6 pl-4 mt-2 space-y-1';
                const wrapper = document.createElement('div');
                wrapper.className = 'mb-2';
                wrapper.appendChild(card);
                wrapper.appendChild(expandContainer);
                folderList.appendChild(wrapper);
                const toggleBtn = card.querySelector('.expand-toggle');
                toggleBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const isExpanded = !expandContainer.classList.contains('hidden');
                    if (isExpanded) {
                        expandContainer.classList.add('hidden');
                        toggleBtn.querySelector('i').setAttribute('data-lucide', 'chevron-right');
                    } else {
                        if (expandContainer.children.length === 0) {
                            expandContainer.innerHTML = '<div class="text-xs text-gray-400 py-2"><i data-lucide="loader" class="w-3 h-3 inline animate-spin"></i> 加载中...</div>';
                            lucide.createIcons();
                            expandContainer.innerHTML = '';
                            await loadChildItems(item.path, expandContainer);
                        }
                        expandContainer.classList.remove('hidden');
                        toggleBtn.querySelector('i').setAttribute('data-lucide', 'chevron-down');
                    }
                    lucide.createIcons();
                });
                card.addEventListener('click', (e) => {
                    if (e.target.closest('.expand-toggle')) return;
                    e.stopPropagation();
                    clearSelection();
                    card.classList.add('selected');
                    selectedFileCard = card;
                    selectedFileCard.item = item;
                    if (defaultHeaderActions) defaultHeaderActions.classList.add('hidden');
                    if (selectedHeaderActions) selectedHeaderActions.classList.remove('hidden');
                    hideContextMenu();
                });
                card.addEventListener('dblclick', () => {
                    currentPath.push(item.name);
                    saveCurrentPath();
                    renderFileSystem();
                });
                card.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    clearSelection();
                    card.classList.add('selected');
                    selectedFileCard = card;
                    selectedFileCard.item = item;
                    if (defaultHeaderActions) defaultHeaderActions.classList.add('hidden');
                    if (selectedHeaderActions) selectedHeaderActions.classList.remove('hidden');
                    showContextMenuAt(e.clientX, e.clientY);
                });
            });
            files.forEach(item => {
                const card = document.createElement('div');
                const iconName = getFileIcon(item.name, 'file');
                const iconColor = getFileIconColor(item.name, 'file');
                const typeDesc = getFileTypeDesc(item.name, 'file');
                card.className = 'file-card bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer flex items-center';
                card.innerHTML = `
                    <div class="w-12 h-12 flex items-center justify-center mr-4 ${iconColor}">
                        <i data-lucide="${iconName}" class="w-8 h-8"></i>
                    </div>
                    <div class="min-w-0 flex-1">
                        <p class="text-sm font-medium truncate">${item.name}</p>
                        <p class="text-[10px] text-gray-400">${typeDesc}</p>
                        <p class="text-[10px] text-gray-400">${formatFileSize(item.size)}</p>
                        <p class="text-[10px] text-gray-400">修改日期: ${formatModificationDate(item.modified)}</p>
                    </div>
                `;
                fileList.appendChild(card);
                // Click handler - check single-click setting
                const singleClickOpen = document.getElementById('personal-single-click')?.checked || false;
                card.addEventListener('click', (e) => {
                    e.stopPropagation();
                    clearSelection();
                    card.classList.add('selected');
                    selectedFileCard = card;
                    selectedFileCard.item = item;
                    if (defaultHeaderActions) defaultHeaderActions.classList.add('hidden');
                    if (selectedHeaderActions) selectedHeaderActions.classList.remove('hidden');
                    hideContextMenu();
                    // Open file on single click if setting is enabled
                    if (singleClickOpen) {
                        openFileInEditor(item);
                    }
                });
                card.addEventListener('dblclick', (e) => {
                    e.stopPropagation();
                    openFileInEditor(item);
                });
                card.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    clearSelection();
                    card.classList.add('selected');
                    selectedFileCard = card;
                    selectedFileCard.item = item;
                    if (defaultHeaderActions) defaultHeaderActions.classList.add('hidden');
                    if (selectedHeaderActions) selectedHeaderActions.classList.remove('hidden');
                    showContextMenuAt(e.clientX, e.clientY);
                });
            });
            lucide.createIcons();
            updateEmptyState();
        } catch (error) {
            hideLoading();
            console.error('[文件系统] 渲染异常:', error);
            showToast('文件列表加载失败: ' + error.message, 'error');
            lucide.createIcons();
            updateEmptyState();
        }
    };
    // --- Editor Initialization ---
    let currentEditorFontSize = 14;
    let isEditorFullscreen = false;
    const getAceMode = (fileName) => {
        const ext = fileName.split('.').pop().toLowerCase();
        const modeMap = {
            'py': 'ace/mode/python',
            'js': 'ace/mode/javascript',
            'ts': 'ace/mode/typescript',
            'json': 'ace/mode/json',
            'html': 'ace/mode/html',
            'htm': 'ace/mode/html',
            'css': 'ace/mode/css',
            'xml': 'ace/mode/xml',
            'md': 'ace/mode/markdown',
            'sql': 'ace/mode/sql',
            'sh': 'ace/mode/sh',
            'bash': 'ace/mode/sh',
            'bat': 'ace/mode/batchfile',
            'ps1': 'ace/mode/powershell',
            'cpp': 'ace/mode/c_cpp',
            'c': 'ace/mode/c_cpp',
            'h': 'ace/mode/c_cpp',
            'java': 'ace/mode/java',
            'go': 'ace/mode/golang',
            'rs': 'ace/mode/rust',
            'php': 'ace/mode/php',
            'rb': 'ace/mode/ruby',
            'yaml': 'ace/mode/yaml',
            'yml': 'ace/mode/yaml',
            'toml': 'ace/mode/toml',
            'csv': 'ace/mode/text',
            'txt': 'ace/mode/text',
            'log': 'ace/mode/text',
            'cfg': 'ace/mode/ini',
            'ini': 'ace/mode/ini',
            'dockerfile': 'ace/mode/dockerfile',
            'vue': 'ace/mode/vue',
            'jsx': 'ace/mode/jsx',
            'tsx': 'ace/mode/tsx',
            'scss': 'ace/mode/scss',
            'sass': 'ace/mode/sass',
            'less': 'ace/mode/less'
        };
        return modeMap[ext] || 'ace/mode/text';
    };
    const getLanguageModeName = (fileName) => {
        const ext = fileName.split('.').pop().toLowerCase();
        const nameMap = {
            'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
            'json': 'JSON', 'html': 'HTML', 'htm': 'HTML',
            'css': 'CSS', 'xml': 'XML', 'md': 'Markdown',
            'sql': 'SQL', 'sh': 'Shell', 'bash': 'Shell',
            'bat': 'Batch', 'ps1': 'PowerShell', 'cpp': 'C++',
            'c': 'C', 'h': 'C/C++ Header', 'java': 'Java',
            'go': 'Go', 'rs': 'Rust', 'php': 'PHP',
            'rb': 'Ruby', 'yaml': 'YAML', 'yml': 'YAML',
            'toml': 'TOML', 'csv': 'CSV', 'txt': '纯文本',
            'log': '日志', 'cfg': '配置', 'ini': 'INI',
            'vue': 'Vue', 'jsx': 'JSX', 'tsx': 'TSX',
            'scss': 'SCSS', 'sass': 'Sass', 'less': 'Less'
        };
        return nameMap[ext] || '纯文本';
    };
    const initEditor = () => {
        editorInstance = ace.edit("editor-container");
        editorInstance.setTheme("ace/theme/chrome");
        editorInstance.setOptions({
            fontSize: currentEditorFontSize + "px",
            showPrintMargin: false,
            showGutter: true,
            highlightActiveLine: true,
            wrap: true,
            enableBasicAutocompletion: true,
            enableLiveAutocompletion: true,
            enableSnippets: true,
            tabSize: 4,
            useSoftTabs: true,
            showInvisibles: false,
            foldStyle: 'markbegin',
            behavioursEnabled: true
        });
        // Track cursor position
        editorInstance.selection.on('changeCursor', () => {
            updateCursorPosition();
        });
        // Track content changes
        editorInstance.session.on('change', () => {
            if (currentEditingItem) {
                const isModified = editorInstance.getValue() !== (currentEditingItem.originalContent || '');
                const indicator = document.getElementById('editor-modified-indicator');
                if (indicator) {
                    indicator.classList.toggle('hidden', !isModified);
                }
            }
        });
        // Add keyboard shortcuts
        // Save: Ctrl+S / Cmd+S
        editorInstance.commands.addCommand({
            name: 'saveFile',
            bindKey: {win: 'Ctrl-S', mac: 'Command-S'},
            exec: function(editor) {
                saveFile();
            },
            readOnly: false
        });
        // Close editor: Esc
        editorInstance.commands.addCommand({
            name: 'closeEditor',
            bindKey: {win: 'Esc', mac: 'Esc'},
            exec: function(editor) {
                closeEditor();
            },
            readOnly: true
        });
        // Find: Ctrl+F / Cmd+F
        editorInstance.commands.addCommand({
            name: 'findInFile',
            bindKey: {win: 'Ctrl-F', mac: 'Command-F'},
            exec: function(editor) {
                editor.execCommand('find');
            },
            readOnly: true
        });
        // Replace: Ctrl+H / Cmd+H
        editorInstance.commands.addCommand({
            name: 'replaceInFile',
            bindKey: {win: 'Ctrl-H', mac: 'Command-Option-F'},
            exec: function(editor) {
                editor.execCommand('replace');
            },
            readOnly: false
        });
        // Go to line: Ctrl+G / Cmd+L
        editorInstance.commands.addCommand({
            name: 'gotoLine',
            bindKey: {win: 'Ctrl-G', mac: 'Command-L'},
            exec: function(editor) {
                editor.execCommand('gotoline');
            },
            readOnly: true
        });
        // Toggle comment: Ctrl+/
        editorInstance.commands.addCommand({
            name: 'toggleComment',
            bindKey: {win: 'Ctrl-/', mac: 'Command-/'},
            exec: function(editor) {
                editor.toggleCommentLines();
            },
            readOnly: false
        });
        // Duplicate line: Ctrl+Shift+D
        editorInstance.commands.addCommand({
            name: 'duplicateLine',
            bindKey: {win: 'Ctrl-Shift-D', mac: 'Command-Shift-D'},
            exec: function(editor) {
                editor.copyLinesDown();
            },
            readOnly: false
        });
        // Delete line: Ctrl+Shift+K
        editorInstance.commands.addCommand({
            name: 'deleteLine',
            bindKey: {win: 'Ctrl-Shift-K', mac: 'Command-Shift-K'},
            exec: function(editor) {
                editor.removeLines();
            },
            readOnly: false
        });
        // Move line up: Alt+Up
        editorInstance.commands.addCommand({
            name: 'moveLineUp',
            bindKey: {win: 'Alt-Up', mac: 'Option-Up'},
            exec: function(editor) {
                editor.moveLinesUp();
            },
            readOnly: false
        });
        // Move line down: Alt+Down
        editorInstance.commands.addCommand({
            name: 'moveLineDown',
            bindKey: {win: 'Alt-Down', mac: 'Option-Down'},
            exec: function(editor) {
                editor.moveLinesDown();
            },
            readOnly: false
        });
        // Select all: Ctrl+A (built-in)
        // Copy: Ctrl+C (built-in)
        // Paste: Ctrl+V (built-in)
        // Cut: Ctrl+X (built-in)
        // Undo: Ctrl+Z (built-in)
        // Redo: Ctrl+Y / Ctrl+Shift+Z (built-in)
        // Font size increase: Ctrl++
        editorInstance.commands.addCommand({
            name: 'increaseFontSize',
            bindKey: {win: 'Ctrl-Plus|Ctrl-Shift-Plus|Ctrl-NumpadPlus', mac: 'Command-Plus|Command-Shift-Plus'},
            exec: function(editor) {
                increaseEditorFontSize();
            },
            readOnly: true
        });
        // Font size decrease: Ctrl+-
        editorInstance.commands.addCommand({
            name: 'decreaseFontSize',
            bindKey: {win: 'Ctrl-Minus|Ctrl-Shift-Minus|Ctrl-NumpadMinus', mac: 'Command-Minus|Command-Shift-Minus'},
            exec: function(editor) {
                decreaseEditorFontSize();
            },
            readOnly: true
        });
        // Fullscreen: F11
        editorInstance.commands.addCommand({
            name: 'toggleFullscreen',
            bindKey: {win: 'F11', mac: 'F11'},
            exec: function(editor) {
                toggleEditorFullscreen();
            },
            readOnly: true
        });
    };
    initEditor();
    const updateCursorPosition = () => {
        const cursor = editorInstance.getCursorPosition();
        const posEl = document.getElementById('editor-cursor-position');
        if (posEl) {
            posEl.textContent = `行 ${cursor.row + 1}, 列 ${cursor.column + 1}`;
        }
    };
    const increaseEditorFontSize = () => {
        if (currentEditorFontSize < 32) {
            currentEditorFontSize += 2;
            editorInstance.setFontSize(currentEditorFontSize + 'px');
            const fontSizeEl = document.getElementById('editor-font-size');
            if (fontSizeEl) fontSizeEl.textContent = currentEditorFontSize + 'px';
        }
    };
    const decreaseEditorFontSize = () => {
        if (currentEditorFontSize > 8) {
            currentEditorFontSize -= 2;
            editorInstance.setFontSize(currentEditorFontSize + 'px');
            const fontSizeEl = document.getElementById('editor-font-size');
            if (fontSizeEl) fontSizeEl.textContent = currentEditorFontSize + 'px';
        }
    };
    const toggleEditorFullscreen = () => {
        const editorView = document.getElementById('editor-view');
        if (!document.fullscreenElement) {
            editorView.requestFullscreen().then(() => {
                isEditorFullscreen = true;
                editorInstance.resize();
            }).catch(err => {
                console.log('Fullscreen error:', err);
            });
        } else {
            document.exitFullscreen().then(() => {
                isEditorFullscreen = false;
                editorInstance.resize();
            });
        }
    };
    const closeEditor = () => {
        const editorView = document.getElementById('editor-view');
        const indicator = document.getElementById('editor-modified-indicator');
        
        // Check if there are unsaved changes
        if (indicator && !indicator.classList.contains('hidden')) {
            if (!confirm('文件有未保存的更改，确定要关闭吗？')) {
                return;
            }
        }
        
        editorView.classList.add('hidden');
        currentEditingItem = null;
        if (isEditorFullscreen && document.fullscreenElement) {
            document.exitFullscreen();
            isEditorFullscreen = false;
        }
    };
    // Bind Toolbar Save Button
    document.getElementById('editor-save-btn').addEventListener('click', (e) => {
        e.preventDefault();
        saveFile();
    });
    // Font size buttons
    document.getElementById('editor-font-increase').addEventListener('click', () => {
        increaseEditorFontSize();
    });
    document.getElementById('editor-font-decrease').addEventListener('click', () => {
        decreaseEditorFontSize();
    });
    // Minimize button
    document.getElementById('editor-minimize-btn').addEventListener('click', () => {
        closeEditor();
    });
    // Copy path button
    document.getElementById('editor-copy-path').addEventListener('click', () => {
        if (currentEditingItem && currentEditingItem.path) {
            navigator.clipboard.writeText(currentEditingItem.path).then(() => {
                showToast('文件路径已复制', 'success', 2000);
            }).catch(() => {
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = currentEditingItem.path;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                showToast('文件路径已复制', 'success', 2000);
            });
        }
    });
    // Fullscreen button
    document.getElementById('editor-fullscreen').addEventListener('click', () => {
        toggleEditorFullscreen();
    });
    // Listen for fullscreen change
    document.addEventListener('fullscreenchange', () => {
        isEditorFullscreen = !!document.fullscreenElement;
        editorInstance.resize();
    });
    // --- UI Utilities ---
    const loadingOverlay = document.getElementById('loading-overlay');
    let loadingCounter = 0;
    const showLoading = () => {
        loadingCounter++;
        loadingOverlay.classList.add('show');
    };
    const hideLoading = () => {
        loadingCounter = Math.max(0, loadingCounter - 1);
        if (loadingCounter === 0) loadingOverlay.classList.remove('show');
    };
    function showToast(message, type, duration) {
        type = type || 'info';
        duration = duration || 4000;
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        const icons = { success: 'check-circle', error: 'alert-circle', info: 'info', loading: 'loader' };
        toast.innerHTML = `<i data-lucide="${icons[type] || 'info'}" class="w-5 h-5 flex-shrink-0"></i><span>${message}</span>`;
        container.appendChild(toast);
        lucide.createIcons();
        if (type !== 'loading') {
            setTimeout(() => {
                toast.classList.add('toast-removing');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
        return toast;
    }
    const fileOps = {
        async execute(name, apiPath, payload, successMsg) {
            showLoading();
            try {
                const response = await fetch(apiPath, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                hideLoading();
                if (data.success) {
                    if (successMsg) showToast(successMsg, 'success');
                    return data;
                } else {
                    showToast(data.error || name + ' 失败', 'error');
                    return null;
                }
            } catch (e) {
                hideLoading();
                showToast('网络错误: ' + name + ' 操作失败 - ' + e.message, 'error');
                return null;
            }
        },
        async refresh() {
            await renderFileSystem();
        },
        async createFolder(name) {
            const result = await this.execute('创建文件夹', '/api/files/create-folder',
                { path: getDirPath(), name },
                '文件夹 ' + name + ' 已创建'
            );
            if (result) await this.refresh();
        },
        async createFile(name) {
            const result = await this.execute('创建文件', '/api/files/create-file',
                { path: getDirPath(), name },
                '文件 ' + name + ' 已创建'
            );
            if (result) await this.refresh();
        },
        async rename(item, newName) {
            if (!newName || newName === item.name) return;
            const result = await this.execute('重命名', '/api/files/rename',
                { path: item.path, new_name: newName },
                '已重命名为 ' + newName
            );
            if (result) { clearSelection(); await this.refresh(); }
        },
        async copy(item, targetDir) {
            const destDir = targetDir || getDirPath();
            const destPath = destDir.replace(/\/$/, '') + '/' + item.name;
            const result = await this.execute('复制', '/api/files/copy',
                { source: item.path, destination: destPath },
                '已复制到 ' + destDir
            );
            if (result) await this.refresh();
        },
        async move(item, targetDir) {
            const destDir = targetDir.replace(/\/$/, '');
            const destPath = destDir + '/' + item.name;
            const result = await this.execute('移动', '/api/files/move',
                { source: item.path, destination: destPath },
                '已移动到 ' + destDir
            );
            if (result) await this.refresh();
        },
        async delete(item) {
            if (!confirm('确定删除 ' + item.name + '？')) return;
            hideContextMenu();
            const result = await this.execute('删除', '/api/files/delete',
                { path: item.path, type: item.type },
                item.name + ' 已删除'
            );
            if (result) { clearSelection(); await this.refresh(); }
        },
        async saveFile(path, content, fileName) {
            return await this.execute('保存', '/api/files/save',
                { path: path, content: content },
                fileName + ' 已保存'
            );
        },
        async readFile(path) {
            try {
                showLoading();
                const response = await fetch('/api/files/read', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path })
                });
                const data = await response.json();
                hideLoading();
                if (data.success) return data.content;
                showToast(data.error || '读取文件失败', 'error');
                return null;
            } catch (e) {
                hideLoading();
                showToast('读取文件失败: ' + e.message, 'error');
                return null;
            }
        }
    };
    const showContextMenuAt = (x, y) => {
        if (!contextMenu) return;
        contextMenu.style.display = 'block';
        const menuWidth = 180;
        const menuHeight = contextMenu.scrollHeight || 280;
        const maxX = window.innerWidth - menuWidth - 5;
        const maxY = window.innerHeight - menuHeight - 5;
        contextMenu.style.left = Math.min(x, maxX) + 'px';
        contextMenu.style.top = Math.min(y, maxY) + 'px';
    };
    const hideContextMenu = () => {
        if (contextMenu) {
            contextMenu.style.display = 'none';
        }
    };
    const clearSelection = () => {
        document.querySelectorAll('.file-card').forEach(card => card.classList.remove('selected'));
        if (defaultHeaderActions) {
            defaultHeaderActions.classList.remove('hidden');
        }
        if (selectedHeaderActions) {
            selectedHeaderActions.classList.add('hidden');
        }
        selectedFileCard = null;
    };
    const updateEmptyState = () => {
        const folderCount = folderList.querySelectorAll('.file-card').length;
        const fileCount = fileList.querySelectorAll('.file-card').length;
        
        foldersSection.classList.toggle('hidden', folderCount === 0);
        filesSection.classList.toggle('hidden', fileCount === 0);
        
        emptyState.classList.toggle('hidden', folderCount > 0 || fileCount > 0);
    };
    // --- File Card Events ---
    const openFileInEditor = async (item) => {
        if (!item || item.type !== 'file') return;
        
        currentEditingItem = item;
        const fileName = item.name;
        
        // Update editor UI
        const editorFilenameEl = document.getElementById('editor-filename');
        const breadcrumbFilenameEl = document.getElementById('breadcrumb-filename');
        const languageModeEl = document.getElementById('editor-language-mode');
        const fileSizeEl = document.getElementById('editor-file-size');
        const modifiedIndicator = document.getElementById('editor-modified-indicator');
        
        if (editorFilenameEl) editorFilenameEl.textContent = fileName;
        if (breadcrumbFilenameEl) breadcrumbFilenameEl.textContent = fileName;
        if (languageModeEl) languageModeEl.textContent = getLanguageModeName(fileName);
        if (fileSizeEl) fileSizeEl.textContent = formatFileSize(item.size || 0);
        if (modifiedIndicator) modifiedIndicator.classList.add('hidden');
        // Set editor mode based on file extension
        const mode = getAceMode(fileName);
        editorInstance.session.setMode(mode);
        // Load file content
        showLoading();
        let fileContent = "";
        if (item.path) {
            fileContent = await fileOps.readFile(item.path) || "";
        }
        hideLoading();
        // Store original content for change detection
        currentEditingItem.originalContent = fileContent;
        currentEditingItem.content = fileContent;
        // Set content and move cursor to start
        editorInstance.setValue(fileContent, -1);
        editorInstance.clearSelection();
        editorInstance.moveCursorTo(0, 0);
        
        // Show editor
        editorView.classList.remove('hidden');
        editorInstance.resize();
        editorInstance.focus();
        
        // Update cursor position display
        updateCursorPosition();
    };
    const bindFileCardEvents = (card, item) => {
        // Right Click
        card.addEventListener('contextmenu', (e) => {
            console.log('Right-click detected on file card:', item.name);
            e.preventDefault();
            clearSelection();
            card.classList.add('selected');
            selectedFileCard = card;
            selectedFileCard.item = item; // Store item reference
            
            // Only update header actions if elements exist
            if (defaultHeaderActions) {
                defaultHeaderActions.classList.add('hidden');
            }
            if (selectedHeaderActions) {
                selectedHeaderActions.classList.remove('hidden');
            }
            // Only show context menu if element exists
            if (contextMenu) {
                showContextMenuAt(e.clientX, e.clientY);
            } else {
                console.error('Context menu element not found');
            }
        });
        // Left Click
        card.addEventListener('click', (e) => {
            e.stopPropagation();
            clearSelection();
            card.classList.add('selected');
            selectedFileCard = card;
            selectedFileCard.item = item; // Store item reference
            // Only update header actions if elements exist
            if (defaultHeaderActions) {
                defaultHeaderActions.classList.add('hidden');
            }
            if (selectedHeaderActions) {
                selectedHeaderActions.classList.remove('hidden');
            }
            hideContextMenu();
        });
        // Double Click to Edit or Enter Folder
        card.addEventListener('dblclick', async () => {
            if (item.type === 'folder') {
                currentPath.push(item.name);
                saveCurrentPath();
                renderFileSystem();
            } else {
                await openFileInEditor(item);
            }
        });
    };
    // Get "Go to target location after copy/move" setting
    function getGoToTargetSetting() {
        const setting = localStorage.getItem('goToTargetAfterCopyMove');
        return setting === 'true';
    }
    
    // Create share modal
    function createShareModal(fileName) {
        // Create modal container
        const modal = document.createElement('div');
        modal.id = 'share-modal';
        modal.className = 'fixed inset-0 z-50 flex items-center justify-center';
        modal.innerHTML = `
            <div class="absolute inset-0 bg-black bg-opacity-50"></div>
            <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6 relative z-10">
                <h2 class="text-xl font-bold text-gray-800 mb-4">分享文件</h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">文件</label>
                        <p class="text-sm text-gray-600">${fileName}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">分享链接</label>
                        <div class="flex">
                            <input type="text" id="share-link" value="http://localhost:8000/share/${Math.random().toString(36).substr(2, 9)}" class="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm" readonly>
                            <button id="copy-link-btn" class="px-4 py-2 bg-blue-500 text-white border border-transparent rounded-r-md hover:bg-blue-600">复制</button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">过期时间</label>
                        <select id="share-expiry" class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 rounded-md sm:text-sm">
                            <option value="1h">1小时</option>
                            <option value="24h">24小时</option>
                            <option value="7d">7天</option>
                            <option value="30d">30天</option>
                            <option value="never">永不过期</option>
                        </select>
                    </div>
                </div>
                <div class="mt-6 flex justify-end space-x-4">
                    <button id="share-cancel-btn" class="px-4 py-2 text-gray-600 hover:text-gray-700 font-medium">取消</button>
                    <button id="share-create-btn" class="px-4 py-2 bg-blue-500 text-white font-medium rounded hover:bg-blue-600">创建分享</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Add event listeners
        document.getElementById('copy-link-btn').addEventListener('click', () => {
            const shareLink = document.getElementById('share-link');
            shareLink.select();
            document.execCommand('copy');
            alert('链接已复制到剪贴板');
        });
        
        document.getElementById('share-cancel-btn').addEventListener('click', () => {
            modal.remove();
        });
        
        document.getElementById('share-create-btn').addEventListener('click', () => {
            alert('分享已创建');
            modal.remove();
        });
        
        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    // --- Core Actions ---
    function getSelectedItem() {
        return selectedFileCard ? selectedFileCard.item : null;
    }
    function getDirPath() {
        return getFullPath();
    }
    const fileActions = {
        share: () => {
            const item = getSelectedItem();
            if (item) createShareModal(item.name);
        },
        rename: async () => {
            const item = getSelectedItem();
            if (!item) return;
            const newName = prompt('重命名:', item.name);
            if (newName) await fileOps.rename(item, newName);
        },
        copy: async () => {
            const item = getSelectedItem();
            if (!item) return;
            const targetFolder = prompt('请输入目标路径 (留空使用当前目录):');
            if (targetFolder !== null) await fileOps.copy(item, targetFolder.trim());
        },
        move: async () => {
            const item = getSelectedItem();
            if (!item) return;
            const targetFolder = prompt('请输入目标目录路径:');
            if (targetFolder) await fileOps.move(item, targetFolder);
        },
        delete: async () => {
            const item = getSelectedItem();
            if (!item) return;
            await fileOps.delete(item);
        },
        download: async () => {
            showToast('开始下载...', 'info');
        },
        info: async () => {
            const item = getSelectedItem();
            if (!item) return;
            showToast('名称: ' + item.name + ' | 类型: ' + (item.type === 'folder' ? '文件夹' : '文件'), 'info', 5000);
        }
    };
    // --- Global Event Listeners ---
    document.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', (e) => {
            const action = el.dataset.action;
            if (fileActions[action]) {
                e.stopPropagation();
                const result = fileActions[action]();
                if (result && typeof result.then === 'function') {
                    showLoading();
                    result.finally(() => hideLoading());
                }
                hideContextMenu();
            }
        });
    });
    document.getElementById('new-folder-btn').addEventListener('click', async (e) => {
        e.preventDefault();
        const name = prompt('文件夹名称:');
        if (name) await fileOps.createFolder(name);
    });
    document.getElementById('new-file-btn').addEventListener('click', async (e) => {
        e.preventDefault();
        const name = prompt('文件名称:');
        if (name) await fileOps.createFile(name);
    });
    document.getElementById('close-editor').addEventListener('click', () => {
        closeEditor();
    });
    // Global keyboard shortcut to close editor with Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !editorView.classList.contains('hidden')) {
            // Only close if not in an ace editor search box or other overlay
            const activeEl = document.activeElement;
            const isAceInput = activeEl && (activeEl.classList.contains('ace_text-input') || activeEl.closest('.ace_search'));
            if (!isAceInput) {
                closeEditor();
            }
        }
    });
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.file-card') && !e.target.closest('#context-menu')) {
            hideContextMenu();
            clearSelection();
        }
    });
    // Prevent right-click on context menu itself
    if (contextMenu) {
        contextMenu.addEventListener('contextmenu', (e) => e.preventDefault());
    }
    
    // Main content area right-click
    const mainContent = document.querySelector('main.content-area');
    if (mainContent) {
        mainContent.addEventListener('contextmenu', (e) => {
            // Only show context menu if not clicking on a file card
            if (!e.target.closest('.file-card')) {
                e.preventDefault();
                clearSelection();
                // Only show context menu if element exists
                if (contextMenu) {
                    showContextMenuAt(e.clientX, e.clientY);
                } else {
                    console.error('Context menu element not found');
                }
            }
        });
    }
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            document.querySelectorAll('.view-content').forEach(v => v.classList.add('hidden'));
            item.classList.add('active');
            document.getElementById(item.dataset.target).classList.remove('hidden');
            
            // If clicking on "我的文件", ensure file system is rendered and right-click menu is active
            if (item.dataset.target === 'my-files-view') {
                if (typeof renderFileSystem === 'function') {
                    renderFileSystem();
                }
            }
        });
    });
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', () => {
            document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.add('hidden'));
            button.classList.add('active');
            document.getElementById(button.dataset.tab).classList.remove('hidden');
        });
    });
    // Numeric Input Logic
    document.querySelectorAll('.num-minus').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const input = btn.parentElement.querySelector('.num-input');
            if (input.value > 0) {
                input.value = parseInt(input.value) - 1;
            }
        });
    });
    document.querySelectorAll('.num-plus').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const input = btn.parentElement.querySelector('.num-input');
            input.value = parseInt(input.value) + 1;
        });
    });
    // Sidebar Settings Redirection
    document.getElementById('sidebar-settings-btn').addEventListener('click', (e) => {
        e.preventDefault();
        // 1. Switch to Personal Settings View
        const personalSettingsNavItem = document.querySelector('.nav-item[data-target="personal-settings-view"]');
        if (personalSettingsNavItem) {
            personalSettingsNavItem.click();
        }
        
        // 2. Switch to Global Settings Tab
        const globalSettingsTabBtn = document.querySelector('.tab-button[data-tab="global-settings"]');
        if (globalSettingsTabBtn) {
            globalSettingsTabBtn.click();
        }
    });
    // Initialize theme
    initTheme();
    
    // 初始化 "Go to target location after copy/move" setting
    const goTargetCheckbox = document.getElementById('personal-go-target');
    if (goTargetCheckbox) {
        const savedSetting = localStorage.getItem('goToTargetAfterCopyMove');
        goTargetCheckbox.checked = savedSetting !== 'false'; // Default to true
    }
    
    // Load saved path from localStorage (Signal Preservation)
    currentPath = loadSavedPath();
    // SSH Connection Management
    let sshRemotePath = '';
    async function checkSshStatus() {
        try {
            const response = await fetch('/api/ssh/status');
            const status = await response.json();
            const dot = document.getElementById('ssh-indicator-dot');
            const text = document.getElementById('ssh-indicator-text');
            if (status.configured && status.connected) {
                dot.className = 'w-2 h-2 rounded-full bg-green-500 mr-2';
                text.textContent = status.message;
                text.className = 'text-xs text-green-600';
                sshRemotePath = status.remote_path || '';
            } else if (status.configured && !status.connected) {
                dot.className = 'w-2 h-2 rounded-full bg-red-500 mr-2';
                text.textContent = status.message;
                text.className = 'text-xs text-red-500';
            } else {
                dot.className = 'w-2 h-2 rounded-full bg-gray-300 mr-2';
                text.textContent = '未配置 - 点击配置';
                text.className = 'text-xs text-gray-400 cursor-pointer';
            }
        } catch (e) {
            console.error('SSH status check failed:', e);
        }
    }
    document.getElementById('ssh-status-bar').addEventListener('click', (e) => {
        if (!e.target.closest('button')) {
            openSshConfig();
        }
    });
    document.getElementById('ssh-config-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        openSshConfig();
    });
    async function openSshConfig() {
        const modal = document.getElementById('ssh-config-modal');
        modal.classList.remove('hidden');
        document.getElementById('ssh-test-result').classList.add('hidden');
        try {
            const response = await fetch('/api/ssh/status');
            const status = await response.json();
            document.getElementById('ssh-host-input').value = status.host || '';
            if (status.port) document.getElementById('ssh-port-input').value = status.port;
            document.getElementById('ssh-user-input').value = status.username || '';
            document.getElementById('ssh-password-input').value = '';
            if (status.remote_path) document.getElementById('ssh-path-input').value = status.remote_path;
        } catch (e) {
            console.error('Failed to load SSH config:', e);
        }
    }
    document.getElementById('ssh-modal-close').addEventListener('click', () => {
        document.getElementById('ssh-config-modal').classList.add('hidden');
    });
    document.getElementById('ssh-config-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget || e.target.classList.contains('bg-opacity-50')) {
            document.getElementById('ssh-config-modal').classList.add('hidden');
        }
    });
    document.getElementById('ssh-test-connect').addEventListener('click', async () => {
        const btn = document.getElementById('ssh-test-connect');
        const resultDiv = document.getElementById('ssh-test-result');
        btn.disabled = true;
        btn.textContent = '测试中...';
        resultDiv.className = 'text-sm';
        resultDiv.classList.remove('hidden');
        resultDiv.textContent = '正在连接...';
        resultDiv.className = 'text-sm text-yellow-600';
        try {
            const response = await fetch('/api/ssh/configure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    host: document.getElementById('ssh-host-input').value,
                    port: parseInt(document.getElementById('ssh-port-input').value) || 22,
                    username: document.getElementById('ssh-user-input').value,
                    password: document.getElementById('ssh-password-input').value,
                    remote_path: document.getElementById('ssh-path-input').value || '/'
                })
            });
            const data = await response.json();
            if (data.success) {
                resultDiv.textContent = '✓ ' + data.message;
                resultDiv.className = 'text-sm text-green-600';
                await checkSshStatus();
                currentPath = [];
                localStorage.removeItem('lastVisitedPath');
                if (sshRemotePath) {
                    currentPath = sshRemotePath.split('/').filter(p => p);
                }
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                document.querySelectorAll('.view-content').forEach(v => v.classList.add('hidden'));
                document.querySelector('[data-target="my-files-view"]').classList.add('active');
                document.getElementById('my-files-view').classList.remove('hidden');
                renderFileSystem();
                setTimeout(() => document.getElementById('ssh-config-modal').classList.add('hidden'), 1500);
            } else {
                resultDiv.textContent = '✗ ' + data.message;
                resultDiv.className = 'text-sm text-red-500';
            }
        } catch (e) {
            resultDiv.textContent = '✗ 请求失败: ' + e.message;
            resultDiv.className = 'text-sm text-red-500';
        } finally {
            btn.disabled = false;
            btn.textContent = '测试并保存';
        }
    });
    // Check SSH status on page load
    document.getElementById('refresh-file-list').addEventListener('click', (e) => {
        e.stopPropagation();
        renderFileSystem();
        showToast('文件列表已刷新', 'info', 2000);
    });
    (async () => {
        await checkSshStatus();
        if (sshRemotePath && currentPath.length === 0) {
            currentPath = sshRemotePath.split('/').filter(p => p);
        }
        renderFileSystem();
    })();
});