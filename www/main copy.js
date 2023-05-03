
// Generate a new user_id every time the user connects
function generateUserId() {
  return window.crypto.randomUUID();
}

// Generate a user ID for the user
const userId = localStorage.getItem('user_id') || generateUserId();
localStorage.setItem('user_id', userId);

// Pointer mouse
document.addEventListener('mousemove', function(e) {
  const streak = document.createElement('div');
  streak.classList.add('streak');
  streak.style.top = e.clientY + 'px';
  streak.style.left = e.clientX + 'px';
  document.body.appendChild(streak);

  setTimeout(function() {
    streak.remove();
  }, 100);
});

// Login form
document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('login-form');
  const usernameInput = document.getElementById('username-input');
  const passwordInput = document.getElementById('password-input');

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const username = usernameInput.value;
    const password = passwordInput.value;

    try {
      const access_token = await login(username, password);
      // Save the access token to local storage
      const user_tokens = JSON.parse(localStorage.getItem('user_tokens')) || {};
      user_tokens[username] = access_token;
      localStorage.setItem('user_tokens', JSON.stringify(user_tokens));
      window.location.href = '/test/index.html';
      console.log(user_token[username])
    } catch (error) {
      alert('Invalid username or password');
      console.error('Error:', error);
    }
  });
});

async function login(username, password) {
  const response = await fetch('http://0.0.0.0:8000/token', {
    mode: 'no-cors',
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      'username': username,
      'password': password,
      'grant_type': '',
      'scope': '',
      'client_id': '',
      'client_secret': ''
    }),
    credentials: 'same-origin'
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
    console.log(response);
  }
  console.log(response);
  const data = await response.json();
  return data.access_token;
}


async function uploadFile() {
  const input = document.getElementById('file');
  const file = input.files[0];
  if (!file) {
    console.log('No file selected');
    return;
  }

  const user_tokens = JSON.parse(localStorage.getItem('user_tokens')) || {};
  const username = 'test'; // replace with the actual username
  const access_token = user_tokens[username];

  const reader = new FileReader();
  reader.readAsArrayBuffer(file);

  reader.onload = async function() {
    const arrayBuffer = reader.result;
    const uint8Array = new Uint8Array(arrayBuffer);
    const response = await fetch('http://0.0.0.0:8000/upload?max_size=1000000', {
      mode: 'no-cors',
      method: 'POST',
      headers: {
        'Authorization': `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxNjgzMTE5ODQwfQ.fEq2vc0Ix4yNfsqgj_hx4vYMJ9zyPvqvNSdaX0m8Zfg`,
        'Content-Type': 'application/octet-stream',
        'accept': 'application/json',
        'Content-Disposition': `attachment; filename=${file.name}`,
        'Content-Length': uint8Array.length
      },
      body: uint8Array
    });

    console.log(response);
  };

  reader.onerror = function() {
    console.log(reader.error);
  };
}



// Question form
document.addEventListener('DOMContentLoaded', (domEvent) => {
  const questionFormEl = document.getElementById('question-form');
  const questionEl = document.getElementById('question');
  const questionBoxEl = document.getElementById('question-box');

  const socket = new WebSocket(`ws://0.0.0.0:8000/ws/${userId}`);

  function handleMessage(data) {
    const message = JSON.parse(data);
    questionAppend(false, message);

    if (message.answer) {
      const answerMessage = { msg: message.answer, userId: null, answer: true };
      questionAppend(false, answerMessage);
    }
  }

  function questionAppend(myQuestion, questionContent){
    let sideOff = 'justify-start',
        bgColorClass = 'bg-slate-700';
  
    if (myQuestion) {
      sideOff = 'justify-end';
      bgColorClass = 'bg-slate-500';
    }
  
    const myString = `
      <div class="w-full flex ${sideOff}">
        <div class="box-bordered p-1 ${bgColorClass} w-8/12 text-slate-100 rounded mb-1">
          <p>${questionContent.msg}</p>
          <p>${questionContent.userId}</p>
        </div>
      </div>
    `;
  
    const domParser = new DOMParser();
    const msgEl = domParser.parseFromString(myString, 'text/html').body.firstElementChild;
  
    if (myQuestion) {
      msgEl.classList.add('user-message');
    } else {
      msgEl.classList.add('bot-message');
    }
  
    questionBoxEl.append(msgEl);
  }
  

  // listen to broadcast_to_room
  document.addEventListener('broadcast_to_room', (event) => {
    const answerMessage = { msg: event.detail.answer, userId: null, answer: true };
    questionAppend(false, answerMessage);
  });

  // listen to websocket
  socket.addEventListener('open', (socketEvent) => {
    console.log('Connection is open')
  });

  socket.addEventListener('close', (socketEvent) => {
    console.log('Connection is close')
  });

  // listen for message
  socket.addEventListener('message', (event) => {
    console.log('Getting a message from server ', event.data);
    handleMessage(event.data);
  });

  // sending some data
  questionFormEl.addEventListener('submit', (event) => {
    // event.preventDefault();

    if (questionEl === '') {
      console.log('Mille sabord !');
    } else {
      socket.send(questionEl.value);
      questionAppend(true, { msg: questionEl.value, userId: null });
      event.target.reset();

      // add listener to wait for the response from server
      socket.addEventListener('message', (event) => {
        const message = JSON.parse(event.data);
        if (message.answer) {
          const answerMessage = { msg: message.answer, userId: null };
          questionAppend(false, answerMessage);
        }
      });
    }
  });
});
