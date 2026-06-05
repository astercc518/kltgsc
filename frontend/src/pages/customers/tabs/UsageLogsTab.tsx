import React from 'react';
const UsageLogsTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-usage">用量日志 (customer {customerId})</div>
);
export default UsageLogsTab;
