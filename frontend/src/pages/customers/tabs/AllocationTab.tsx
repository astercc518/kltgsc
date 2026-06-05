import React from 'react';
const AllocationTab: React.FC<{ customerId: number }> = ({ customerId }) => (
  <div data-testid="tab-allocation">资源分配 (customer {customerId})</div>
);
export default AllocationTab;
