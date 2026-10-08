import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import AdminTaskManager from './AdminTaskManager';
import { eventRegistrations } from '../../api/registrations';
import { listEvents } from '../../api/events';
import { eventTasks, updateTask } from '../../api/tasks';

jest.mock('../../api/registrations', () => ({ eventRegistrations: jest.fn() }));
jest.mock('../../api/events', () => ({ listEvents: jest.fn() }));
jest.mock('../../api/tasks', () => ({
  createEventTask: jest.fn(),
  eventTasks: jest.fn(),
  updateTask: jest.fn(),
}));

test('shows a failed task edit inside the edit modal', async () => {
  listEvents.mockResolvedValue({ data: { results: [{ id: 1, title: 'Community picnic' }] } });
  eventRegistrations.mockResolvedValue({ data: { results: [], next: null } });
  eventTasks.mockResolvedValue({
    data: {
      count: 1,
      results: [{
        id: 7,
        title: 'Set up tables',
        description: 'Arrange the tables.',
        priority: 'medium',
        status: 'todo',
        assignee: null,
        due_at: null,
      }],
    },
  });
  updateTask.mockRejectedValue({ response: { status: 400, data: { detail: 'Task update failed.' } } });

  render(<AdminTaskManager />);
  await screen.findByText('Choose an event');
  fireEvent.change(screen.getByLabelText('Event'), { target: { value: '1' } });
  await screen.findByText('Set up tables');
  fireEvent.click(screen.getByRole('button', { name: 'Edit details' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save task' }));

  const dialog = screen.getByRole('dialog', { name: 'Edit task' });
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Task update failed.');
  await waitFor(() => expect(updateTask).toHaveBeenCalledWith(7, expect.objectContaining({ title: 'Set up tables' })));
});
