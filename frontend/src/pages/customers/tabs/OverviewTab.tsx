import React from 'react';
const OverviewTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-overview">概览 (customer {customerId})</div>
);
export default OverviewTab;
