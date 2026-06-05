import React from 'react';
const BillingTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-billing">订阅账单 (customer {customerId})</div>
);
export default BillingTab;
