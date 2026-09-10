// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { it, expect, vi } from 'vitest';
import DownloadLimitModal from './DownloadLimitModal';
import { rememberExport, pendingExport } from '../lib/authReturn';
import { exportTable } from '../lib/api';
vi.mock('../context/authContext', () => ({ useAuth: () => ({ isAuthed: true }) }));
vi.mock('../lib/api', () => ({ exportTable: vi.fn(async () => ({ blob: new Blob(['csv']), remaining: null })) }));
vi.mock('../lib/track', () => ({ trackFile: vi.fn(), track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({ useT: () => key => key }));
it('offers explicit completion on the original page after authentication', async () => {
  history.replaceState(null, '', '/indicator/cpi?mode=inflation');
  const payload = { format: 'csv', filename: 'cpi.csv', points: [{ date: '2025-01-01', actual: 8.2 }] };
  rememberExport(payload);
  URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  render(<MemoryRouter initialEntries={['/indicator/cpi?mode=inflation']}><DownloadLimitModal /></MemoryRouter>);
  const button = await screen.findByRole('button', { name: 'download.resume.action' });
  expect(exportTable).not.toHaveBeenCalled();
  fireEvent.click(button);
  await waitFor(() => expect(exportTable).toHaveBeenCalledWith(payload));
  await waitFor(() => expect(pendingExport()).toBeNull());
});
