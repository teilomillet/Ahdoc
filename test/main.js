// pointer souris
document.addEventListener('mousemove', function(e) {
	var streak = document.createElement('div');
	streak.classList.add('streak');
	streak.style.top = e.clientY + 'px';
	streak.style.left = e.clientX + 'px';
	document.body.appendChild(streak);


	setTimeout(function() {
		streak.remove();
	}, 1000);
});


// uploading file
function uploadFile() {
  var input = document.getElementById("file");
  var file = input.files[0];
  var formData = new FormData();
  formData.append("file", file);
  fetch("http://vps-e30509de.vps.ovh.net:8000/upload", {
    mode: 'no-cors',
    method: "POST",
    body: formData
  })
  .then(data => console.log(data))
}

// add event listener
document.addEventListener('DOMContentLoaded', (domEvent)=>{
  domEvent.preventDefault();

  const questionFormEl = document.getElementById('question-form');
  const questionEl = document.getElementById('question');
  const questionBoxEl = document.getElementById('question-box');

  const userId = window.crypto.randomUUID();

  const socket = new WebSocket(`ws://vps-e30509de.vps.ovh.net:8000/ws/${userId}`);

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
        bgColor = 'bg-slate-700',
        specificUser = userId;
    
    if (myQuestion) {
      sideOff = 'justify-end';
      bgColor = 'bg-slate-500';
    } else {
      specificUser = questionContent.userId;
    }

    const msgType = questionContent.answer ? 'answer' : 'question';
    const bgColorClass = msgType === 'question' ? bgColor : 'bg-green-500';
    const message = msgType === 'question' ? questionContent.msg : questionContent.answer;
  
    const myString = `
      <div class="w-full flex ${sideOff}">
        <div class="box-bordered p-1 ${bgColorClass} w-8/12 text-slate-100 rounded mb-1">
          <p>${message}</p>
          <p>${specificUser}</p>
        </div>
      </div>
    `;
  
    const domParser = new DOMParser();
    const msgEl = domParser.parseFromString(myString, 'text/html').body.firstElementChild;
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
