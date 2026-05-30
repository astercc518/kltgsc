/**
 * usePortalStatsWebsocket — customer portal WS for stats invalidation.
 * Replaces 30s polling with reactive push.
 */
import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getCustomerToken } from '../auth';

export function usePortalStatsWebsocket() {
  const qc = useQueryClient();
  React.useEffect(() => {
    const token = getCustomerToken();
    if (!token) return;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/ws?token=${token}`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'portal_stats_update') {
          qc.invalidateQueries({ queryKey: ['portal-stats'] });
        }
      } catch { /* ignore */ }
    };
    ws.onerror = () => { /* swallow */ };
    return () => { ws.close(); };
  }, [qc]);
}
