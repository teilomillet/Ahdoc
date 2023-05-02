const chatHistory = document.querySelector('.chat-history');
const sendBtn = document.getElementById('send-btn');

sendBtn.addEventListener('click', () => {
  const message = document.querySelector('.chat-input input').value;
  if (message.trim() !== '') {
    // Send the message to the server and append to chat history
    fetch('/upload', {
      method: 'POST',
      body: JSON.stringify({ message }),
      headers: {
        'Content-Type': 'application/json'
      }
    })
    .then(response => response.json())
    .then(data => {
      const messageDiv = document.createElement('div');
      messageDiv.classList.add('message');
      messageDiv.innerHTML = `
        <div class="sender">${data.sender}</div>
        <div class="text">${data.message}</div>
      `;
      chatHistory.appendChild(messageDiv);
    })
    .catch(error => console.error(error));
    document.querySelector('.chat-input input').value = '';
  }
});