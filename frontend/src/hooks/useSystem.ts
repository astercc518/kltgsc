/**
 * 系统相关 Hooks
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../lib/queryClient';
import {
  checkHealth,
  getOverviewStats,
  getDailyTrend,
  getOperationLogs,
  getSystemConfig,
  setSystemConfig,
} from '../services/api';

/**
 * 健康检查
 */
export function useHealthCheck() {
  return useQuery({
    queryKey: queryKeys.system.health,
    queryFn: checkHealth,
    staleTime: 30 * 1000, // 30秒
    refetchInterval: 60 * 1000, // 每分钟自动刷新
  });
}

/**
 * 获取总览统计
 */
export function useOverviewStats() {
  return useQuery({
    queryKey: queryKeys.system.stats,
    queryFn: getOverviewStats,
    staleTime: 60 * 1000, // 1分钟
    refetchInterval: 60 * 1000, // 每分钟自动刷新
  });
}

/**
 * 获取每日趋势数据
 */
export function useDailyTrend(days: number = 7) {
  return useQuery({
    queryKey: queryKeys.system.dailyTrend(days),
    queryFn: () => getDailyTrend(days),
    staleTime: 5 * 60 * 1000, // 5分钟
  });
}

/**
 * 获取操作日志
 */
export function useOperationLogs(skip: number = 0, limit: number = 20, action?: string) {
  return useQuery({
    queryKey: queryKeys.logs.list({ skip, limit, action }),
    queryFn: () => getOperationLogs(skip, limit, action),
    staleTime: 30 * 1000, // 30秒
  });
}

/**
 * 获取系统配置
 */
export function useSystemConfig() {
  return useQuery({
    queryKey: queryKeys.system.config,
    queryFn: getSystemConfig,
    staleTime: 5 * 60 * 1000, // 5分钟
  });
}

/**
 * 设置系统配置
 */
export function useSetSystemConfig() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ key, value, description }: { key: string; value: string; description?: string }) =>
      setSystemConfig(key, value, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.system.config });
    },
  });
}

// 定义统计数据类型
export interface OverviewStats {
  accounts: {
    total: number;
    active: number;
    banned: number;
    survival_rate: number;
  };
  messages: {
    today_sent: number;
  };
  leads: {
    total: number;
    new_today: number;
  };
}

export interface DailyTrendData {
  date: string;
  success: number;
  failed: number;
  total: number;
}
