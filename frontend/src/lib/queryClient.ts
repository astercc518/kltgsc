/**
 * React Query 配置
 */
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 数据过期时间 (5分钟)
      staleTime: 5 * 60 * 1000,
      
      // 缓存时间 (30分钟)
      gcTime: 30 * 60 * 1000,
      
      // 重试配置
      retry: 2,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      
      // 窗口聚焦时不自动重新获取 (减少服务器压力)
      refetchOnWindowFocus: false,
      
      // 网络重连时重新获取
      refetchOnReconnect: true,
    },
    mutations: {
      // 突变重试配置
      retry: 1,
    },
  },
});

// 查询键常量
export const queryKeys = {
  // 账号相关
  accounts: {
    all: ['accounts'] as const,
    list: (params?: { skip?: number; limit?: number; status?: string; role?: string }) => 
      ['accounts', 'list', params] as const,
    detail: (id: number) => ['accounts', 'detail', id] as const,
    count: (status?: string) => ['accounts', 'count', status] as const,
  },
  
  // 代理相关
  proxies: {
    all: ['proxies'] as const,
    list: (params?: { skip?: number; limit?: number; status?: string; category?: string }) => 
      ['proxies', 'list', params] as const,
    count: (status?: string, category?: string) => ['proxies', 'count', status, category] as const,
  },
  
  // 系统相关
  system: {
    health: ['system', 'health'] as const,
    config: ['system', 'config'] as const,
    stats: ['system', 'stats'] as const,
    dailyTrend: (days: number) => ['system', 'dailyTrend', days] as const,
    securityInfo: ['system', 'security'] as const,
    encryptionStatus: ['system', 'encryptionStatus'] as const,
  },
  
  // 日志相关
  logs: {
    all: ['logs'] as const,
    list: (params?: { skip?: number; limit?: number; action?: string }) => 
      ['logs', 'list', params] as const,
  },
  
  // 任务相关
  tasks: {
    all: ['tasks'] as const,
    active: ['tasks', 'active'] as const,
    status: (taskId: string) => ['tasks', 'status', taskId] as const,
    batch: (taskIds: string[]) => ['tasks', 'batch', taskIds] as const,
  },
  
  // 采集相关
  scraping: {
    tasks: ['scraping', 'tasks'] as const,
    users: (params?: { skip?: number; limit?: number; sourceGroup?: string }) => 
      ['scraping', 'users', params] as const,
    usersCount: (sourceGroup?: string) => ['scraping', 'usersCount', sourceGroup] as const,
  },
  
  // CRM 相关
  crm: {
    leads: (params?: { skip?: number; limit?: number; status?: string }) => 
      ['crm', 'leads', params] as const,
    lead: (id: number) => ['crm', 'lead', id] as const,
  },
  
  // 监控相关
  monitors: {
    all: ['monitors'] as const,
    hits: (params?: { skip?: number; limit?: number }) => ['monitors', 'hits', params] as const,
  },
  
  // 养号相关
  warmup: {
    tasks: ['warmup', 'tasks'] as const,
    templates: ['warmup', 'templates'] as const,
  },
  
  // 脚本相关
  scripts: {
    all: ['scripts'] as const,
    tasks: ['scripts', 'tasks'] as const,
  },
  
  // 拉人相关
  invites: {
    tasks: ['invites', 'tasks'] as const,
  },
};
