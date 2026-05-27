// 全局错误处理
window.addEventListener('error', function(e) {
    console.error('全局错误捕获:', e.error);
    console.error('错误信息:', e.message);
    console.error('错误文件:', e.filename);
    console.error('错误行号:', e.lineno);
    console.error('错误列号:', e.colno);
    
    // 显示用户友好的错误提示
    if (e.message.includes('tailwind') || e.message.includes('remixicon')) {
        showToast('样式资源加载失败，请检查网络连接', 'warning');
    }
});

// 资源加载错误处理
window.addEventListener('load', function() {
    // 检查关键资源是否加载成功
    setTimeout(function() {
        checkCriticalResources();
    }, 2000);
});

function checkCriticalResources() {
    // 检查 Tailwind CSS
    const testElement = document.createElement('div');
    testElement.className = 'hidden';
    document.body.appendChild(testElement);
    const tailwindLoaded = window.getComputedStyle(testElement).display === 'none';
    document.body.removeChild(testElement);
    
    if (!tailwindLoaded) {
        console.warn('Tailwind CSS 未正确加载');
        showToast('样式框架加载失败，页面可能显示异常', 'warning');
    }
    
    // 检查 RemixIcon
    const iconElement = document.createElement('i');
    iconElement.className = 'ri-home-line';
    document.body.appendChild(iconElement);
    const iconLoaded = window.getComputedStyle(iconElement).fontFamily === 'remixicon';
    document.body.removeChild(iconElement);
    
    if (!iconLoaded) {
        console.warn('RemixIcon 字体未正确加载');
        showToast('图标字体加载失败，部分图标可能无法显示', 'warning');
    }
}

// 网络请求错误处理
function handleApiError(error, context) {
    console.error(`API 请求失败 [${context}]:`, error);
    
    let message = '网络请求失败';
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
        message = '网络连接失败，请检查服务器状态';
    } else if (error.status === 401) {
        message = '登录状态已过期，请重新登录';
    } else if (error.status === 404) {
        message = '请求的资源不存在';
    } else if (error.status >= 500) {
        message = '服务器内部错误';
    }
    
    showToast(message, 'error');
}

// 改进的 fetch 包装器
window.safeFetch = async function(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            timeout: options.timeout || 10000, // 10秒超时
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return response;
    } catch (error) {
        handleApiError(error, url);
        throw error;
    }
};