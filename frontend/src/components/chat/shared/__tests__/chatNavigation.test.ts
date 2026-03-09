import {
  getNewChatUrl,
  getSelectedThreadUrl,
} from '../chatNavigation';

describe('chatNavigation', () => {
  it('keeps live chat navigation on /chat with a thread query param', () => {
    expect(getSelectedThreadUrl('thread-123')).toBe('/chat?thread=thread-123');
  });

  it('uses the plain chat route for new chats', () => {
    expect(getNewChatUrl()).toBe('/chat');
  });
});
