import { Account, Proxy, TaskStatus, WarmupTemplate } from '../../services/api';

export interface ImportTask {
  taskId: string;
  url: string;
  status: string; // PENDING, STARTED, SUCCESS, FAILURE, PROGRESS
  progress?: {
    status: string;
    message: string;
    url: string;
  };
  result?: any;
  error?: string;
}

export interface AccountStats {
  total: number;
  active: number;
  init: number;
  banned: number;
}

export interface PaginationState {
  current: number;
  pageSize: number;
  total: number;
}
