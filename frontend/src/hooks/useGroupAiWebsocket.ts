/**
 * useGroupAiWebsocket — listen for `ai_suggestion_pending` events.
 * On message: refetch inbox + show toast notification.
 *
 * Uses the same WS endpoint pattern as connectWebSocket in services/api.ts:
 *   /api/v1/ws?token=<jwt>
 */
import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { notification } from 'antd';

export function useGroupAiWebsocket(customerId?: number) {
  const qc = useQueryClient();
  React.useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'ai_suggestion_pending') {
          if (customerId !== undefined && msg.customer_id !== customerId) return;
          qc.invalidateQueries({ queryKey: ['admin-inbox-group-ai', msg.customer_id] });
          notification.info({
            message: 'AI 草稿待审',
            description: `#${msg.pending_reply_id}: ${(msg.suggested_text || '').slice(0, 50)}...`,
          });
        }
      } catch {
        // 非 JSON 或非本类型，忽略
      }
    };

    ws.onerror = () => {
      // ws 失败不要 throw / crash UI；admin 仍能 manual refresh
    };

    return () => { ws.close(); };
  }, [customerId, qc]);
}
