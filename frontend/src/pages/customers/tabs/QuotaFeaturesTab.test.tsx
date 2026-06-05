import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from 'antd';
import QuotaFeaturesTab from './QuotaFeaturesTab';
import * as svc from '../../../services/adminCustomers';

vi.mock('../../../services/adminCustomers', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminCustomers')>(
    '../../../services/adminCustomers',
  );
  return {
    ...actual,
    upsertCustomerFeature: vi.fn().mockResolvedValue({
      feature_slug: 'ai_marketing',
      enabled: false,
      unit_price_cents: 0,
      is_custom_price: false,
      billing_unit: 'call',
      name_zh: 'AI 营销',
      name_en: 'AI Marketing',
      category: 'ai',
      notes: '',
    }),
    listFeatureRegistry: vi.fn().mockResolvedValue([
      {
        slug: 'ai_marketing',
        name_zh: 'AI 营销',
        name_en: 'AI Marketing',
        description: 'AI marketing',
        billing_unit: 'call',
        default_price_cents: 0,
        enabled_by_default: true,
        category: 'ai',
        is_active: true,
      },
    ]),
    listCustomerFeatures: vi.fn().mockResolvedValue([
      {
        feature_slug: 'ai_marketing',
        enabled: true,
        unit_price_cents: 0,
        is_custom_price: false,
        billing_unit: 'call',
        name_zh: 'AI 营销',
        name_en: 'AI Marketing',
        category: 'ai',
        notes: '',
      },
    ]),
    getCustomerById: vi.fn().mockResolvedValue({
      id: 7,
      account_used: 2,
      account_quota: 5,
      group_used: 100,
      group_quota: 500,
      token_used: 0,
      token_quota: 2000000,
      seat_used: 1,
      seat_quota: 1,
    }),
  };
});

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <App>
        <QuotaFeaturesTab customerId={7} />
      </App>
    </QueryClientProvider>,
  );
}

describe('QuotaFeaturesTab', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('toggling a feature off calls upsertCustomerFeature with enabled=false', async () => {
    const user = userEvent.setup();
    renderTab();
    const toggle = await screen.findByRole('switch');
    await user.click(toggle);
    await waitFor(() =>
      expect(svc.upsertCustomerFeature).toHaveBeenCalledWith(
        7,
        'ai_marketing',
        expect.objectContaining({ enabled: false }),
      ),
    );
  });
});
