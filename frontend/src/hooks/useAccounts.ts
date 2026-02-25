/**
 * 账号相关 Hooks
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../lib/queryClient';
import {
  getAccounts,
  getAccountCount,
  getAccount,
  deleteAccount,
  deleteAccountsBatch,
  checkAccountStatus,
  checkAccountsBatch,
  updateAccountRole,
  updateAccountsRoleBatch,
  Account,
} from '../services/api';

interface AccountListParams {
  skip?: number;
  limit?: number;
  status?: string;
  role?: string;
}

/**
 * 获取账号列表
 */
export function useAccounts(params: AccountListParams = {}) {
  return useQuery({
    queryKey: queryKeys.accounts.list(params),
    queryFn: () => getAccounts(params.skip, params.limit, params.status, params.role),
    staleTime: 30 * 1000, // 30秒
  });
}

/**
 * 获取账号数量
 */
export function useAccountCount(status?: string) {
  return useQuery({
    queryKey: queryKeys.accounts.count(status),
    queryFn: () => getAccountCount(status),
    staleTime: 60 * 1000, // 1分钟
  });
}

/**
 * 获取单个账号详情
 */
export function useAccount(id: number) {
  return useQuery({
    queryKey: queryKeys.accounts.detail(id),
    queryFn: () => getAccount(id),
    enabled: id > 0,
  });
}

/**
 * 删除账号
 */
export function useDeleteAccount() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => deleteAccount(id),
    onSuccess: () => {
      // 刷新账号列表
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
    },
  });
}

/**
 * 批量删除账号
 */
export function useDeleteAccountsBatch() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (accountIds: number[]) => deleteAccountsBatch(accountIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
    },
  });
}

/**
 * 检查账号状态
 */
export function useCheckAccountStatus() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => checkAccountStatus(id),
    onSuccess: () => {
      // 延迟刷新，等待后台任务完成
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      }, 3000);
    },
  });
}

/**
 * 批量检查账号状态
 */
export function useCheckAccountsBatch() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (accountIds: number[]) => checkAccountsBatch(accountIds),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
      }, 5000);
    },
  });
}

/**
 * 更新账号角色
 */
export function useUpdateAccountRole() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ accountId, role, tags }: { accountId: number; role: string; tags?: string }) =>
      updateAccountRole(accountId, role, tags),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.detail(variables.accountId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
    },
  });
}

/**
 * 批量更新账号角色
 */
export function useUpdateAccountsRoleBatch() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ accountIds, role, tags, tier }: { 
      accountIds: number[]; 
      role: string; 
      tags?: string;
      tier?: string;
    }) => updateAccountsRoleBatch(accountIds, role, tags, tier),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
    },
  });
}
