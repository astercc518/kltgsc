import axios from 'axios';

// --- Axios Instance ---
const api = axios.create({
    baseURL: '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
});

// --- Request Interceptor: 自动添加 Authorization header ---
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// --- Response Interceptor: 401 错误时跳转登录页 ---
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401 || error.response?.status === 403) {
            // 清除无效 token
            localStorage.removeItem('token');
            // 跳转到登录页（避免在登录页循环跳转）
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

// --- Interfaces ---

export interface HealthStatus {
    status: string;
    message: string;
}

export interface Account {
    id: number;
    phone_number: string;
    status: string;
    proxy_id?: number;
    proxy?: Proxy;
    created_at: string;
    last_active?: string;
    cooldown_until?: string;
    auto_reply?: boolean;
    persona_prompt?: string;
    device_model?: string;
    system_version?: string;
    app_version?: string;
    api_id?: number;
    api_hash?: string;
    session_file_path?: string;
    session_string?: string;
    role?: string;
    tags?: string;
    tier?: string;
}

export interface AccountCreate {
    phone_number: string;
    api_id?: number;
    api_hash?: string;
    session_string?: string;
}

export interface Proxy {
    id: number;
    ip: string;
    port: number;
    protocol: string;
    username?: string;
    password?: string;
    status: string;
    category: string;
    provider_type: string;
    created_at: string;
    last_checked?: string;
    latency?: number;
    country?: string;
}

export interface ProxyCreate {
    ip: string;
    port: number;
    protocol: string;
    username?: string;
    password?: string;
    category?: string;
    provider_type?: string;
}

export interface TargetUser {
    id: number;
    telegram_id: number;
    username?: string;
    first_name?: string;
    last_name?: string;
    phone?: string;
    source_group?: string;
    created_at: string;
}

export interface SendTask {
    id: number;
    name: string;
    status: string;
    total_count: number;
    success_count: number;
    fail_count: number;
    created_at: string;
    min_delay?: number;
    max_delay?: number;
    message_content: string;
}

export interface SystemConfig {
    key: string;
    value: string;
    description?: string;
    updated_at?: string;
}

export interface Lead {
    id: number;
    account_id: number;
    telegram_user_id: number;
    username?: string;
    first_name?: string;
    last_name?: string;
    phone?: string;
    status: string;
    tags_json: string;
    notes?: string;
    last_interaction_at: string;
    created_at: string;
}

export interface LeadInteraction {
    id: number;
    lead_id: number;
    direction: string;
    message_type: string;
    content: string;
    created_at: string;
}

export interface Script {
    id: number;
    name: string;
    description?: string;
    roles: any[];
    lines: Line[];
    created_at: string;
}

export interface Line {
    role: string;
    content: string;
    delay?: number;
}

export interface ScriptTask {
    id: number;
    script_id: number;
    status: string;
    group_link: string;
    created_at: string;
}

export interface WarmupTask {
    id: number;
    status: string;
    account_count: number;
    created_at: string;
    completed_at?: string;
}

export interface TaskStatus {
    task_id: string;
    status: string;
    result?: any;
}

export interface CreateTaskPayload {
    name: string;
    message_content: string;
    account_ids: number[];
    target_user_ids: number[];
    min_delay?: number;
    max_delay?: number;
}

// --- Common/Health ---

export const checkHealth = async (): Promise<HealthStatus> => {
    const response = await api.get('/health');
    return response.data;
};

// --- Auth ---

export const login = async (username: string, password: string): Promise<any> => {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    const response = await api.post('/login/access-token', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return response.data;
};

// --- Dashboard / System ---

export const getOverviewStats = async (): Promise<any> => {
    const response = await api.get('/system/stats/overview');
    return response.data;
};

export const getDailyTrend = async (days: number = 7): Promise<any[]> => {
    const response = await api.get(`/system/stats/daily_trend?days=${days}`);
    return response.data;
};

export const getOperationLogs = async (skip: number = 0, limit: number = 20, action?: string): Promise<any[]> => {
    const params: any = { skip, limit };
    if (action) params.action = action;
    const response = await api.get('/logs/', { params });
    return response.data;
};

// --- System Config ---

export const getSystemConfig = async (): Promise<SystemConfig[]> => {
    const response = await api.get('/system/config');
    return response.data;
};

export const getSystemConfigByKey = async (key: string): Promise<SystemConfig> => {
    const response = await api.get(`/system/config/${key}`);
    return response.data;
};

export const setSystemConfig = async (key: string, value: string, description?: string): Promise<SystemConfig> => {
    const response = await api.post('/system/config', { key, value, description });
    return response.data;
};

// --- Accounts ---

export const getAccounts = async (skip: number = 0, limit: number = 20, status?: string, role?: string): Promise<Account[]> => {
    const params: any = { skip, limit };
    if (status) params.status = status;
    if (role) params.role = role;
    const response = await api.get('/accounts/', { params });
    return response.data;
};

export const getAccountCount = async (status?: string): Promise<{ total: number; status?: string }> => {
    const params: any = {};
    if (status) params.status = status;
    const response = await api.get('/accounts/count', { params });
    return response.data;
};

export const getAccount = async (id: number): Promise<Account> => {
    const response = await api.get(`/accounts/${id}`);
    return response.data;
};

export const createAccount = async (account: AccountCreate): Promise<Account> => {
    const response = await api.post('/accounts', account);
    return response.data;
};

export const updateAccountRole = async (accountId: number, role: string, tags?: string): Promise<Account> => {
    const response = await api.put(`/accounts/${accountId}/role`, { role, tags });
    return response.data;
};

export const updateAccountsRoleBatch = async (accountIds: number[], role: string, tags?: string, tier?: string): Promise<any> => {
    const response = await api.post('/accounts/batch/role', { account_ids: accountIds, role, tags, tier });
    return response.data;
};

export const deleteAccount = async (id: number): Promise<void> => {
    await api.delete(`/accounts/${id}`);
};

export const deleteAccountsBatch = async (accountIds: number[]): Promise<{ message: string; deleted_count: number }> => {
    const response = await api.post('/accounts/batch/delete', { account_ids: accountIds });
    return response.data;
};

export const uploadAccountSession = async (file: File, phoneNumber?: string): Promise<Account> => {
    const formData = new FormData();
    formData.append('file', file);
    if (phoneNumber) formData.append('phone_number', phoneNumber);
    const response = await api.post('/accounts/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
};

export const uploadAccountSessionsBatch = async (files: File[]): Promise<any> => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    const response = await api.post('/accounts/batch/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
};

export const checkAccountStatus = async (id: number): Promise<{ task_id: string; message: string }> => {
    const response = await api.post(`/accounts/${id}/check`);
    return response.data;
};

export const checkAccountsBatch = async (accountIds: number[]): Promise<any> => {
    const response = await api.post('/accounts/batch/check', { account_ids: accountIds });
    return response.data;
};

// SpamBot 深度检测
export interface SpamBotCheckResult {
    account_id: number;
    phone: string;
    status: 'clean' | 'restricted' | 'error';
    is_restricted: boolean;
    restriction_type: 'none' | 'temporary' | 'permanent' | 'unknown';
    restriction_reason?: string;
    expires_at?: string;
    raw_response?: string;
    error?: string;
}

export const checkSpamBotStatus = async (accountId: number): Promise<SpamBotCheckResult> => {
    const response = await api.post(`/accounts/${accountId}/spambot-check`);
    return response.data;
};

export const updateAccountProxy = async (accountId: number, proxyId: number): Promise<Account> => {
    const response = await api.put(`/accounts/${accountId}/proxy`, { proxy_id: proxyId });
    return response.data;
};

export const sendTestMessageBatch = async (accountIds: number[], username: string, message: string): Promise<any> => {
    const response = await api.post('/accounts/batch/send_message', {
        account_ids: accountIds,
        username,
        message
    });
    return response.data;
};

export const updateAccountProfile = async (accountId: number, data: { first_name?: string; last_name?: string; about?: string; random?: boolean }): Promise<any> => {
    const response = await api.post(`/accounts/${accountId}/update_profile`, data);
    return response.data;
};

export const updateAccountUsername = async (accountId: number, username: string): Promise<any> => {
    const response = await api.post(`/accounts/${accountId}/update_username`, { username });
    return response.data;
};

export const updateAccount2FA = async (accountId: number, data: { password: string; current_password?: string; hint?: string }): Promise<any> => {
    const response = await api.post(`/accounts/${accountId}/update_2fa`, data);
    return response.data;
};

export const updateAccountPhoto = async (accountId: number, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(`/accounts/${accountId}/update_photo`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
};

export const updateAccountPhotoRandom = async (accountId: number): Promise<any> => {
    const response = await api.post(`/accounts/${accountId}/update_photo/random`);
    return response.data;
};

export const autoUpdateAccount = async (accountId: number, options: { update_profile?: boolean; update_photo?: boolean; update_2fa?: boolean; update_username?: boolean; password_2fa?: string }): Promise<any> => {
    const response = await api.post(`/accounts/${accountId}/auto_update`, options);
    return response.data;
};

export const updateAccountAIConfig = async (accountId: number, config: { auto_reply: boolean; persona_prompt?: string }): Promise<any> => {
    const response = await api.put(`/accounts/${accountId}/ai_config`, config);
    return response.data;
};

export const importMegaAccounts = async (
    urls: string[],
    target_channels?: string,
    auto_check: boolean = false,
    auto_warmup: boolean = false
): Promise<{ task_ids: string[]; urls: string[]; message: string }> => {
    const response = await api.post('/accounts/import/mega', { urls, target_channels, auto_check, auto_warmup });
    return response.data;
};

// --- Proxies ---

export const getProxies = async (skip: number = 0, limit: number = 20, status?: string, category?: string): Promise<Proxy[]> => {
    const params: any = { skip, limit };
    if (status) params.status = status;
    if (category) params.category = category;
    const response = await api.get('/proxies/', { params });
    return response.data;
};

export const getProxyCount = async (status?: string, category?: string): Promise<{ total: number; status?: string }> => {
    const params: any = {};
    if (status) params.status = status;
    if (category) params.category = category;
    const response = await api.get('/proxies/count', { params });
    return response.data;
};

export const createProxy = async (proxy: ProxyCreate): Promise<Proxy> => {
    const response = await api.post('/proxies', proxy);
    return response.data;
};

export const deleteProxy = async (id: number): Promise<void> => {
    await api.delete(`/proxies/${id}`);
};

export const uploadProxies = async (fileOrText: File | string, category: string = 'static', providerType: string = 'datacenter'): Promise<any> => {
    let proxiesText: string;
    
    if (fileOrText instanceof File) {
        // 如果是文件，读取文件内容
        proxiesText = await fileOrText.text();
    } else {
        // 如果是字符串，直接使用
        proxiesText = fileOrText;
    }
    
    const response = await api.post('/proxies/batch/upload', { 
        proxies_text: proxiesText,
        category: category,
        provider_type: providerType
    });
    return response.data;
};

export const checkProxy = async (id: number): Promise<any> => {
    const response = await api.post(`/proxies/${id}/check`);
    return response.data;
};

export const checkProxiesBatch = async (proxyIds: number[]): Promise<any> => {
    const response = await api.post('/proxies/batch/check', { proxy_ids: proxyIds });
    return response.data;
};

export const deleteProxiesBatch = async (proxyIds: number[]): Promise<any> => {
    const response = await api.post('/proxies/batch/delete', { proxy_ids: proxyIds });
    return response.data;
};

export const syncIP2World = async (apiUrl?: string, category: string = 'static', providerType: string = 'datacenter'): Promise<any> => {
    const response = await api.post('/proxies/sync/ip2world', { 
        api_url: apiUrl, 
        category,
        provider_type: providerType 
    });
    return response.data;
};

export const refreshProxiesFromIP2World = async (): Promise<any> => {
    const response = await api.post('/proxies/refresh/ip2world');
    return response.data;
};

// --- Scraping ---

export const joinGroup = async (accountId: number, groupLink: string): Promise<any> => {
    const response = await api.post('/scraping/join', { account_id: accountId, group_link: groupLink });
    return response.data;
};

export const joinGroupsBatch = async (accountIds: number[], groupLinks: string[]): Promise<any> => {
    const response = await api.post('/scraping/join/batch', { account_ids: accountIds, group_links: groupLinks });
    return response.data;
};

export interface ScrapingTask {
    id: number;
    task_type: string;
    status: string;
    account_ids_json: string;
    group_links_json: string;
    result_json: string;
    success_count: number;
    fail_count: number;
    error_message?: string;
    celery_task_id?: string;
    created_at: string;
    completed_at?: string;
}

export const getScrapingTasks = async (skip: number = 0, limit: number = 20, taskType?: string): Promise<ScrapingTask[]> => {
    const params: any = { skip, limit };
    if (taskType) params.task_type = taskType;
    const response = await api.get('/scraping/tasks', { params });
    return response.data;
};

export const getScrapingTaskDetail = async (taskId: number): Promise<any> => {
    const response = await api.get(`/scraping/tasks/${taskId}`);
    return response.data;
};

export const scrapeMembers = async (accountId: number, groupLink: string, limit: number = 100): Promise<any> => {
    const response = await api.post('/scraping/scrape', { account_id: accountId, group_link: groupLink, limit });
    return response.data;
};

export interface ScrapeBatchFilters {
    active_only?: boolean;
    has_photo?: boolean;
    has_username?: boolean;
}

export const scrapeMembersBatch = async (
    accountIds: number[], 
    groupLinks: string[], 
    limit: number = 100,
    filters: ScrapeBatchFilters = {}
): Promise<{ task_id: string; scraping_task_id: number; message: string }> => {
    const response = await api.post('/scraping/scrape/batch', { 
        account_ids: accountIds, 
        group_links: groupLinks,
        limit,
        filter_active_only: filters.active_only || false,
        filter_has_photo: filters.has_photo || false,
        filter_has_username: filters.has_username || false
    });
    return response.data;
};

export const getTargetUsers = async (skip: number = 0, limit: number = 50, sourceGroup?: string): Promise<TargetUser[]> => {
    const params: any = { skip, limit };
    if (sourceGroup) params.source_group = sourceGroup;
    const response = await api.get('/scraping/users', { params });
    return response.data;
};

export const getTargetUsersCount = async (sourceGroup?: string): Promise<number> => {
    const params: any = {};
    if (sourceGroup) params.source_group = sourceGroup;
    const response = await api.get('/scraping/users/count', { params });
    return response.data.total;
};

// --- Marketing ---

export const createSendTask = async (payload: CreateTaskPayload): Promise<SendTask> => {
    const response = await api.post('/marketing/tasks', payload);
    return response.data;
};

export const getMarketingTasks = async (skip: number = 0, limit: number = 20): Promise<SendTask[]> => {
    const response = await api.get('/marketing/tasks', { params: { skip, limit } });
    return response.data;
};

// --- Task Management ---

export const getTaskStatus = async (taskId: string): Promise<TaskStatus> => {
    const response = await api.get(`/tasks/${taskId}`);
    return response.data;
};

export const getTasksBatch = async (taskIds: string[]): Promise<Record<string, TaskStatus>> => {
    const response = await api.post('/tasks/batch', { task_ids: taskIds });
    return response.data.tasks;
};

export const getActiveTasks = async (): Promise<any> => {
    const response = await api.get('/tasks/active');
    return response.data;
};

export const revokeTask = async (taskId: string): Promise<any> => {
    const response = await api.post(`/tasks/${taskId}/revoke`);
    return response.data;
};

// --- Registration ---

export const startAutoRegistration = async (options: { count: number; country?: string }): Promise<any> => {
    const response = await api.post('/registration/auto', options);
    return response.data;
};

// --- AI ---

// AI 配置类型
export interface AIConfigData {
    id: number;
    name: string;
    provider: string;
    base_url: string;
    model: string;
    is_default: boolean;
    is_active: boolean;
    created_at: string;
    updated_at: string;
    has_api_key: boolean;
}

export interface AIConfigCreate {
    name: string;
    provider: string;
    api_key: string;
    base_url?: string;
    model: string;
    is_default?: boolean;
}

export interface AIConfigUpdate {
    name?: string;
    provider?: string;
    api_key?: string;
    base_url?: string;
    model?: string;
    is_default?: boolean;
    is_active?: boolean;
}

// 获取所有 AI 配置
export const getAIConfigs = async (activeOnly: boolean = false): Promise<AIConfigData[]> => {
    const response = await api.get('/ai/configs', { params: { active_only: activeOnly } });
    return response.data;
};

// 获取单个 AI 配置
export const getAIConfig = async (id: number): Promise<AIConfigData> => {
    const response = await api.get(`/ai/configs/${id}`);
    return response.data;
};

// 创建 AI 配置
export const createAIConfig = async (data: AIConfigCreate): Promise<AIConfigData> => {
    const response = await api.post('/ai/configs', data);
    return response.data;
};

// 更新 AI 配置
export const updateAIConfig = async (id: number, data: AIConfigUpdate): Promise<AIConfigData> => {
    const response = await api.put(`/ai/configs/${id}`, data);
    return response.data;
};

// 删除 AI 配置
export const deleteAIConfig = async (id: number): Promise<void> => {
    await api.delete(`/ai/configs/${id}`);
};

// 设置默认 AI 配置
export const setDefaultAIConfig = async (id: number): Promise<void> => {
    await api.put(`/ai/configs/${id}/default`);
};

// 测试指定 AI 配置连接
export const testAIConfigConnection = async (id: number): Promise<any> => {
    const response = await api.post(`/ai/configs/${id}/test`);
    return response.data;
};

// 测试默认 AI 连接（兼容旧接口）
export const testAIConnection = async (): Promise<any> => {
    const response = await api.get('/ai/test_connection');
    return response.data;
};

// --- Leads / CRM ---

export const getLeads = async (skip: number = 0, limit: number = 20, status?: string): Promise<Lead[]> => {
    const params: any = { skip, limit };
    if (status) params.status = status;
    const response = await api.get('/crm/leads', { params });
    return response.data;
};

export const getLead = async (id: number): Promise<Lead> => {
    const response = await api.get(`/crm/leads/${id}`);
    return response.data;
};

export const updateLead = async (id: number, data: Partial<Lead>): Promise<Lead> => {
    const response = await api.put(`/crm/leads/${id}`, data);
    return response.data;
};

export const sendLeadMessage = async (leadId: number, content: string): Promise<any> => {
    const response = await api.post(`/crm/leads/${leadId}/send`, { content });
    return response.data;
};

export const connectWebSocket = (onMessage: (data: any) => void): WebSocket | null => {
    const token = localStorage.getItem('token');
    if (!token) {
        console.error('WebSocket connection failed: No token available');
        return null;
    }
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        // 如果是认证失败，跳转到登录页
        if (event.code === 4001 || event.code === 4002 || event.code === 4003) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
    };
    
    return ws;
};

// --- Scripts ---

export const getScripts = async (): Promise<Script[]> => {
    const response = await api.get('/scripts');
    return response.data;
};

export const createScript = async (data: { name: string; description?: string; roles: any[]; topic: string; line_count?: number }): Promise<Script> => {
    const response = await api.post('/scripts', data);
    return response.data;
};

export const generateScriptLines = async (scriptId: number): Promise<any> => {
    const response = await api.post(`/scripts/${scriptId}/generate`);
    return response.data;
};

export const getScriptTasks = async (): Promise<ScriptTask[]> => {
    const response = await api.get('/scripts/tasks');
    return response.data;
};

export const createScriptTask = async (data: { script_id: number; account_ids: number[]; group_link: string }): Promise<ScriptTask> => {
    const response = await api.post('/scripts/tasks', data);
    return response.data;
};

// --- Warmup ---

export interface WarmupTemplate {
    id: number;
    name: string;
    description?: string;
    action_type: string;
    min_delay: number;
    max_delay: number;
    duration_minutes: number;
    target_channels: string;
    is_default: boolean;
    created_at: string;
    updated_at: string;
}

export const getWarmupTasks = async (): Promise<WarmupTask[]> => {
    const response = await api.get('/warmup/tasks');
    return response.data;
};

export const createWarmupTask = async (data: { 
    name: string;
    account_ids: number[]; 
    action_type: string; 
    min_delay?: number; 
    max_delay?: number;
    duration_minutes?: number;
    target_channels?: string;
}): Promise<WarmupTask> => {
    const response = await api.post('/warmup/tasks', data);
    return response.data;
};

// --- Warmup Templates ---

export const getWarmupTemplates = async (): Promise<WarmupTemplate[]> => {
    const response = await api.get('/warmup/templates');
    return response.data;
};

export const createWarmupTemplate = async (data: {
    name: string;
    description?: string;
    action_type: string;
    min_delay: number;
    max_delay: number;
    duration_minutes: number;
    target_channels: string;
    is_default?: boolean;
}): Promise<WarmupTemplate> => {
    const response = await api.post('/warmup/templates', data);
    return response.data;
};

export const updateWarmupTemplate = async (id: number, data: Partial<WarmupTemplate>): Promise<WarmupTemplate> => {
    const response = await api.put(`/warmup/templates/${id}`, data);
    return response.data;
};

export const deleteWarmupTemplate = async (id: number): Promise<void> => {
    await api.delete(`/warmup/templates/${id}`);
};


export interface KeywordMonitor {
    id: number;
    keyword: string;
    match_type: string;  // partial, exact, regex, semantic
    target_groups?: string;
    action_type: string;
    reply_script_id?: number;
    is_active: boolean;
    description?: string;
    created_at: string;
    // 被动功能
    forward_target?: string;
    ai_reply_prompt?: string;
    cooldown_seconds?: number;
    auto_capture_lead?: boolean;
    score_weight?: number;
    // 被动式营销 - 语义匹配
    scenario_description?: string;
    auto_keywords?: string;
    similarity_threshold?: number;
    // 主动式营销
    marketing_mode?: string;  // passive, active
    reply_mode?: string;      // group_reply, private_dm
    delay_min_seconds?: number;
    delay_max_seconds?: number;
    enable_account_rotation?: boolean;
    max_replies_per_day?: number;
    ai_persona?: string;      // helpful, expert, curious, custom
}

export interface KeywordMonitorCreate {
    keyword: string;
    match_type: string;
    target_groups?: string;
    action_type: string;
    reply_script_id?: number;
    is_active?: boolean;
    description?: string;
    forward_target?: string;
    ai_reply_prompt?: string;
    cooldown_seconds?: number;
    auto_capture_lead?: boolean;
    score_weight?: number;
    scenario_description?: string;
    auto_keywords?: string;
    similarity_threshold?: number;
    marketing_mode?: string;
    reply_mode?: string;
    delay_min_seconds?: number;
    delay_max_seconds?: number;
    enable_account_rotation?: boolean;
    max_replies_per_day?: number;
    ai_persona?: string;
}

export interface KeywordMonitorUpdate {
    keyword?: string;
    match_type?: string;
    target_groups?: string;
    action_type?: string;
    reply_script_id?: number;
    is_active?: boolean;
    description?: string;
    forward_target?: string;
    ai_reply_prompt?: string;
    cooldown_seconds?: number;
    auto_capture_lead?: boolean;
    score_weight?: number;
    scenario_description?: string;
    auto_keywords?: string;
    similarity_threshold?: number;
    marketing_mode?: string;
    reply_mode?: string;
    delay_min_seconds?: number;
    delay_max_seconds?: number;
    enable_account_rotation?: boolean;
    max_replies_per_day?: number;
    ai_persona?: string;
}

export interface KeywordHit {
    id: number;
    keyword_monitor_id: number;
    source_group_id: string;
    source_group_name?: string;
    source_user_id: string;
    source_user_name?: string;
    message_content: string;
    detected_at: string;
    status: string;
}

// --- Keyword Monitor ---

export const getKeywordMonitors = async (skip: number = 0, limit: number = 100): Promise<KeywordMonitor[]> => {
    const response = await api.get('/monitors/', { params: { skip, limit } });
    return response.data;
};

export const createKeywordMonitor = async (data: KeywordMonitorCreate): Promise<KeywordMonitor> => {
    const response = await api.post('/monitors/', data);
    return response.data;
};

export const updateKeywordMonitor = async (id: number, data: KeywordMonitorUpdate): Promise<KeywordMonitor> => {
    const response = await api.put(`/monitors/${id}`, data);
    return response.data;
};

export const deleteKeywordMonitor = async (id: number): Promise<void> => {
    await api.delete(`/monitors/${id}`);
};

export const getKeywordHits = async (skip: number = 0, limit: number = 50): Promise<KeywordHit[]> => {
    const response = await api.get('/monitors/hits', { params: { skip, limit } });
    return response.data;
};


export interface InviteTask {
    id: number;
    name: string;
    target_channel: string;
    source_group?: string;
    status: string;
    account_ids_json: string;
    target_user_ids_json: string;
    success_count: number;
    fail_count: number;
    max_invites_per_account: number;
    created_at: string;
}

export interface InviteTaskCreate {
    name: string;
    target_channel: string;
    source_group?: string;
    account_ids: number[];
    target_user_ids: number[];
    max_invites_per_account?: number;
}

// --- Invite Tasks ---

export const getInviteTasks = async (): Promise<InviteTask[]> => {
    const response = await api.get('/invites/tasks');
    return response.data;
};

export const createInviteTask = async (data: InviteTaskCreate): Promise<InviteTask> => {
    const response = await api.post('/invites/tasks', data);
    return response.data;
};

// === 用户管理 ===

export interface ChangePasswordRequest {
    current_password: string;
    new_password: string;
    confirm_password: string;
}

export interface ChangePasswordResponse {
    success: boolean;
    message: string;
}

export interface UserInfo {
    id: number;
    username: string;
    is_active: boolean;
    is_superuser: boolean;
}

export const getCurrentUser = async (): Promise<UserInfo> => {
    const response = await api.get('/users/me');
    return response.data;
};

export const changePassword = async (data: ChangePasswordRequest): Promise<ChangePasswordResponse> => {
    const response = await api.post('/users/change-password', data);
    return response.data;
};

export default api;


