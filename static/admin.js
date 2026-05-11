  function openConfirm(uid, name) {
    document.getElementById("confirm-uid").value = uid;
    document.getElementById("confirm-name").innerText = name;
    document.getElementById("confirm-overlay").classList.add("show");
  }
  function closeConfirm() {
    document.getElementById("confirm-overlay").classList.remove("show");
  }