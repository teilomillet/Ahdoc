// pointer souris
document.addEventListener('mousemove', function(e) {
	var streak = document.createElement('div');
	streak.classList.add('streak');
	streak.style.top = e.clientY + 'px';
	streak.style.left = e.clientX + 'px';
	document.body.appendChild(streak);


	setTimeout(function() {
		streak.remove();
	}, 500);
});

// uploading file
function uploadFile() {
  event.preventDefault();
  console.log("uploadFile() function called");
  const input = document.getElementById("file");
  const file = input.files[0];
  const formData = new FormData();
  formData.append("file", file, file.name);
  fetch("https://ssl.ahdoc.chat/upload", {
    mode: 'no-cors',
    method: "POST",
    body: formData
  })
  .then(console.log('send.'), console.log('not send.'))
  .then(data => {
    console.log(data);
    // Do something with the response data
  })
}




document.addEventListener("DOMContentLoaded", () => {
  const socket = new WebSocket("wss://ssl.ahdoc.chat/chat");

const questionForm = document.getElementById("question-form");
const questionInput = document.getElementById("question");
const questionBox = document.getElementById("question-box");

questionForm.addEventListener("submit", event => {
  event.preventDefault();
  const message = questionInput.value.trim();
  if (message) {
    socket.send(message);
    questionBox.insertAdjacentHTML(
      "beforeend",
      `<div class="message message-sent">
        <p>${message}</p>
      </div>`
    );
    questionInput.value = "";
  }
});

socket.addEventListener("message", event => {
  const message = JSON.parse(event.data).msg;
  questionBox.insertAdjacentHTML(
    "beforeend",
    `<div class="message message-received">
      <p>${message}</p>
    </div>`
  );
});
});


