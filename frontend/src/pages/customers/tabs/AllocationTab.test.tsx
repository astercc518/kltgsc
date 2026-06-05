import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from 'antd';
import AllocationTab from './AllocationTab';
import * as svc from '../../../services/adminCustomers';

vi.mock('../../../services/adminCustomers', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminCustomers')>(
    '../../../services/adminCustomers',
  );
  return {
    ...actual,
    reallocateAccounts: vi.fn(),
    reallocateGroups: vi.fn(),
    regenerateKb: vi.fn(),
    getCustomerById: vi.fn().mockResolvedValue({
      id: 7,
      email: 'a@b.io',
      account_used: 3,
      account_quota: 3,
      group_used: 100,
      group_quota: 500,
    }),
  };
});

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <App>
        <AllocationTab customerId={7} />
      </App>
    </QueryClientProvider>,
  );
}

describe('AllocationTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('cancel does NOT call reallocate API', async () => {
    const user = userEvent.setup();
    renderTab();
    await user.click(await screen.findByRole('button', { name: /重新分配账号/ }));
    // AntD v6 inserts spaces between CJK chars in buttons: "取消" → "取 消"
    await user.click(await screen.findByRole('button', { name: /取.?消/ }));
    expect(svc.reallocateAccounts).not.toHaveBeenCalled();
  });

  it('confirm calls reallocateAccounts with the customer id', async () => {
    (svc.reallocateAccounts as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderTab();
    await user.click(await screen.findByRole('button', { name: /重新分配账号/ }));
    // AntD v6 inserts spaces between CJK chars in buttons: "确认" → "确 认"
    await user.click(await screen.findByRole('button', { name: /确.?认/ }));
    await waitFor(() => expect(svc.reallocateAccounts).toHaveBeenCalledWith(7));
  });
});
