// Generate a new user_id every time the user connects
function generateUserId() {
  return window.crypto.randomUUID();
}

// pointer souris
document.addEventListener('mousemove', function(e) {
  var streak = document.createElement('div');
  streak.classList.add('streak');
  streak.style.top = e.clientY + 'px';
  streak.style.left = e.clientX + 'px';
  document.body.appendChild(streak);

  setTimeout(function() {
    streak.remove();
  }, 100);
});

// signup request
const signupForm = document.querySelector('#signup-form');
signupForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const username = document.querySelector('#username').value;
  const password = document.querySelector('#password').value;
  const email = document.querySelector('#email').value;
  
  const formData = new FormData();
  formData.append('username', username);
  formData.append('password', password);
  formData.append('email', email);
  
  const response = await fetch('http://0.0.0.0:8000/users/signup', {
    mode: 'no-cors',
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  alert(result.message);
});

// uploading file
function uploadFile() {
  var input = document.getElementById("file");
  var file = input.files[0];
  if (!file) {
    console.log('No file selected');
    return;
  }
  var formData = new FormData();
  formData.append("file", file, file.name);
  fetch("http://0.0.0.0:8000/upload", {
    mode: 'no-cors',
    method: "POST",
    body: formData
  })
  .then(data => console.log(data))
  .catch(error => console.log(error));
}

// add event listener
document.addEventListener('DOMContentLoaded', (domEvent)=>{
  // domEvent.preventDefault();

  const questionFormEl = document.getElementById('question-form');
  const questionEl = document.getElementById('question');
  const questionBoxEl = document.getElementById('question-box');
  
  const user_id = generateUserId(); // Generate a new user_id every time the user connects

  const socket = new WebSocket(`ws://0.0.0.0:8000/ws/${user_id}`);

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
    event.preventDefault();

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
