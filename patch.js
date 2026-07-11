const fs = require('fs');
const file = 'frontend/src/hooks/__tests__/useChatStreaming.threadScope.test.tsx';
let content = fs.readFileSync(file, 'utf8');
content = content.replace(
  'messages: [] as ChatPageMessage[],',
  'messages: [] as ChatPageMessage[],\n    displayedMessages: [] as ChatPageMessage[],'
);
fs.writeFileSync(file, content);
