import React from 'react';
const QuotaFeaturesTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-quota">配额功能 (customer {customerId})</div>
);
export default QuotaFeaturesTab;
