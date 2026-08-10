import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LangProvider } from '@/i18n';
import Header from './Header';

afterEach(() => {
  cleanup();
  document.body.style.overflow = '';
  document.body.style.position = '';
  document.body.style.top = '';
  document.body.style.width = '';
});

describe('Header mobile menu', () => {
  it('locks body scroll while open and restores on close', () => {
    render(
      <MemoryRouter>
        <LangProvider>
          <Header />
        </LangProvider>
      </MemoryRouter>,
    );

    expect(document.body.style.overflow).toBe('');

    fireEvent.click(screen.getByLabelText('Open menu'));
    expect(document.body.style.overflow).toBe('hidden');
    expect(document.body.style.position).toBe('fixed');

    fireEvent.click(screen.getByLabelText('Close menu'));
    expect(document.body.style.overflow).toBe('');
    expect(document.body.style.position).toBe('');
  });
});
