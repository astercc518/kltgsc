/// <reference types="@testing-library/jest-dom" />
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import NewCustomerPage from './NewCustomerPage';
import * as svc from '../../services/adminCustomers';

vi.mock('../../services/adminCustomers', async () => {
  const actual = await vi.importActual<typeof import('../../services/adminCustomers')>(
    '../../services/adminCustomers',
  );
  return { ...actual, quickProvision: vi.fn(), listCustomers: vi.fn() };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <NewCustomerPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * AntD v6 Select renders two layers:
 *   1. A hidden accessible listbox (role="option") — no click handler
 *   2. A visible popup with .ant-select-item-option divs — has the React onClick handler
 * We must click the visible popup option via fireEvent to avoid blur-triggered close.
 */
async function selectAntOption(
  user: ReturnType<typeof userEvent.setup>,
  combobox: HTMLElement,
  optionText: string,
) {
  await user.click(combobox);
  const option = await waitFor(() => {
    const opts = document.querySelectorAll('.ant-select-item-option');
    const found = Array.from(opts).find((o) => o.textContent?.trim() === optionText);
    if (!found) throw new Error(`AntD Select option "${optionText}" not visible`);
    return found;
  });
  fireEvent.click(option);
}

describe('NewCustomerPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (svc.listCustomers as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it('submits valid form and shows credentials modal', async () => {
    (svc.quickProvision as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 42,
      email: 'alice@acme.io',
      name: 'alice',
      industry: 'crypto',
      plan: 'starter',
      status: 'active',
    });
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByLabelText('Email'), 'alice@acme.io');
    await user.type(screen.getByLabelText('初始密码'), 'Sup3rSecret!');
    // AntD v6 Select: open with userEvent, pick visible popup option with fireEvent
    await selectAntOption(user, screen.getByRole('combobox', { name: '行业' }), 'crypto');
    // AntD Radio wraps label text; getByRole('radio', { name }) works
    await user.click(screen.getByRole('radio', { name: /Starter/ }));
    await user.click(screen.getByRole('button', { name: '开户并激活' }));
    expect(await screen.findByText(/客户已创建并激活/)).toBeInTheDocument();
    expect(screen.getByText('alice@acme.io')).toBeInTheDocument();
    expect(screen.getByText('Sup3rSecret!')).toBeInTheDocument();
  });

  it('blocks submission when email already exists', async () => {
    (svc.listCustomers as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id: 1, email: 'alice@acme.io', status: 'active' },
    ]);
    const user = userEvent.setup();
    renderPage();
    const emailInput = screen.getByLabelText('Email');
    await user.type(emailInput, 'alice@acme.io');
    await user.tab();  // act-aware blur (advances focus off the input)
    expect(await screen.findByText(/邮箱已存在/)).toBeInTheDocument();
  });
});
