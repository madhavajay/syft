let availablePlugins = [];

function loadPlugins() {
  axios
    .get("/plugins")
    .then((response) => {
      availablePlugins = response.data.plugins;
      updatePluginList();
    })
    .catch((error) => console.error("Error loading plugins:", error));
}

function updatePluginList() {
  const pluginList = document.getElementById("pluginList");
  pluginList.innerHTML = "";
  availablePlugins.forEach((plugin) => {
    const div = document.createElement("div");
    div.className = "plugin-item";
    div.innerHTML = `
            <h3>${plugin.name}</h3>
            <p class="plugin-description">${
              plugin.description || "No description available."
            }</p>
            <div class="plugin-controls">
                <input type="number" value="${
                  plugin.default_schedule
                }" placeholder="Schedule (ms)">
                <button onclick="launchPlugin('${
                  plugin.name
                }', this.previousElementSibling.value)">
                    ${plugin.is_running ? "Restart" : "Launch"}
                </button>
            </div>
        `;
    pluginList.appendChild(div);
  });
}

function loadRunningPlugins() {
  axios
    .get("/running")
    .then((response) => {
      const running = response.data.running_plugins;
      const runningList = document.getElementById("runningPlugins");
      runningList.innerHTML = "";
      Object.entries(running).forEach(([plugin, data]) => {
        const div = document.createElement("div");
        div.className = "running-item";
        div.innerHTML = `
                    <span>${plugin}</span>
                    <span>Running: ${
                      data.is_running
                    }, Time: ${data.run_time.toFixed(2)}s, Schedule: ${
                      data.schedule
                    }ms</span>
                    <button onclick="killPlugin('${plugin}')">Kill</button>
                `;
        runningList.appendChild(div);
      });
      availablePlugins.forEach((plugin) => {
        plugin.is_running = plugin.name in running;
      });
      updatePluginList();
    })
    .catch((error) => console.error("Error loading running plugins:", error));
}

function launchPlugin(plugin, schedule) {
  axios
    .post("/launch", { plugin_name: plugin, schedule: parseInt(schedule) })
    .then((response) => {
      console.log(response.data.message);
      loadRunningPlugins();
    })
    .catch((error) => console.error("Error launching plugin:", error));
}

function killPlugin(plugin) {
  axios
    .post("/kill", { plugin_name: plugin })
    .then((response) => {
      console.log(response.data.message);
      loadRunningPlugins();
    })
    .catch((error) => console.error("Error killing plugin:", error));
}

function viewSharedState() {
  console.log("Fetching shared state...");
  axios
    .get("/state")
    .then((response) => {
      console.log("Shared State:", response.data);
      document.getElementById("stateDisplay").textContent = JSON.stringify(
        response.data,
        null,
        2,
      );

      // Update input fields
      const syftboxInput = document.getElementById("syftbox_folderInput");
      const syftInput = document.getElementById("syft_folderInput");

      if (syftboxInput && response.data.syftbox_folder) {
        syftboxInput.value = response.data.syftbox_folder;
      }
      if (syftInput && response.data.syft_folder) {
        syftInput.value = response.data.syft_folder;
      }
    })
    .catch((error) => {
      console.error("Error fetching shared state:", error);
      document.getElementById("stateDisplay").textContent =
        "Error fetching shared state";
    });
}

function updateSharedStateField(key) {
  const input = document.getElementById(`${key}Input`);
  if (!input) {
    console.error(`Input element for ${key} not found`);
    return;
  }
  const value = input.value;
  console.log(`Attempting to update ${key} with value: ${value}`);

  axios
    .post("/state/update", { key, value })
    .then((response) => {
      console.log(`Server response for ${key} update:`, response.data);
      if (response.data.message) {
        alert(response.data.message);
        // Update the input field and refresh the state display
        document.getElementById(`${key}Input`).value = value;
        viewSharedState();
      } else {
        throw new Error("Unexpected server response");
      }
    })
    .catch((error) => {
      console.error(`Error updating ${key}:`, error);
      alert(
        `Error updating ${key}: ${
          error.response ? error.response.data.error : error.message
        }`,
      );
      // Revert the input field to the previous value
      viewSharedState();
    });
}

function loadDatasites() {
  axios
    .get("/datasites")
    .then((response) => {
      const datasiteList = document.getElementById("datasiteList");
      datasiteList.innerHTML = "";
      response.data.datasites.forEach((datasite) => {
        const li = document.createElement("li");
        li.textContent = datasite;
        const deleteButton = document.createElement("button");
        deleteButton.textContent = "Delete";
        deleteButton.onclick = () => removeDatasite(datasite);
        li.appendChild(deleteButton);
        datasiteList.appendChild(li);
      });
    })
    .catch((error) => console.error("Error loading datasites:", error));
}

function addDatasite() {
  const name = document.getElementById("newDatasiteInput").value;
  if (!name) {
    alert("Please enter a datasite name");
    return;
  }
  axios
    .post("/datasites", { name: name })
    .then((response) => {
      alert(response.data.message);
      loadDatasites();
      document.getElementById("newDatasiteInput").value = "";
    })
    .catch((error) => {
      console.error("Error adding datasite:", error);
      alert(error.response.data.error || "Failed to add datasite");
    });
}

function removeDatasite(name) {
  if (confirm(`Are you sure you want to delete the datasite "${name}"?`)) {
    axios
      .delete(`/datasites/${name}`)
      .then((response) => {
        alert(response.data.message);
        loadDatasites();
      })
      .catch((error) => {
        console.error("Error removing datasite:", error);
        alert(error.response.data.error || "Failed to remove datasite");
      });
  }
}

// Modify the window.onload function
window.onload = function () {
  loadPlugins();
  loadRunningPlugins();
  viewSharedState();
  loadDatasites(); // Initial load of datasites
  setInterval(loadRunningPlugins, 5000);
  setInterval(viewSharedState, 5000);
  setInterval(loadDatasites, 5000); // Add this line to update datasites every 5 seconds
};
