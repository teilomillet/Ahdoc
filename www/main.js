// pointer souris
document.addEventListener('mousemove', function(e) {
	var streak = document.createElement('div');
	streak.classList.add('streak');
	streak.style.top = e.clientY + 'px';
	streak.style.left = e.clientX + 'px';
	document.body.appendChild(streak);


	setTimeout(function() {
		streak.remove();
	}, 230);
});

// uploading file
function uploadFile() {
  var input = document.getElementById("file");
  var file = input.files[0];
  var formData = new FormData();
  formData.append("file", file);
  fetch("http://0.0.0.0:8000/upload", {
    mode: 'no-cors',
    method: "POST",
    body: formData
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log(data);
    // Do something with the response data
  })
  .catch(error => {
    console.error('Error:', error);
    // Handle errors here
  });
}


document.addEventListener("DOMContentLoaded", () => {
  const socket = new WebSocket("ws://0.0.0.0:8000/chat");

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


