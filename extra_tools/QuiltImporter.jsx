// After Effects Script: Multi-Camera Quilt Importer
// Place this file in: After Effects > Scripts > ScriptUI Panels
// Or run via File > Scripts > Run Script File

(function createQuiltImporter() {
    
    // Create UI Panel
    var panel = new Window("dialog", "Multi-Camera Quilt Importer");
    panel.orientation = "column";
    panel.alignChildren = "fill";
    
    // Folder selection
    var folderGroup = panel.add("group");
    folderGroup.orientation = "row";
    folderGroup.add("statictext", undefined, "Animation Folder:");
    var folderButton = folderGroup.add("button", undefined, "Browse...");
    var folderPath = null;
    
    // Quilt settings
    var settingsGroup = panel.add("group");
    settingsGroup.orientation = "column";
    settingsGroup.alignChildren = "left";
    
    settingsGroup.add("statictext", undefined, "Quilt Layout:");
    var layoutGroup = settingsGroup.add("group");
    layoutGroup.orientation = "row";
    var widthInput = layoutGroup.add("edittext", undefined, "5");
    widthInput.characters = 3;
    layoutGroup.add("statictext", undefined, "x");
    var heightInput = layoutGroup.add("edittext", undefined, "9");
    heightInput.characters = 3;
    
    // Resolution settings
    var resGroup = settingsGroup.add("group");
    resGroup.orientation = "row";
    resGroup.add("statictext", undefined, "Individual Camera Resolution:");
    var resWidthInput = resGroup.add("edittext", undefined, "1920");
    resWidthInput.characters = 5;
    resGroup.add("statictext", undefined, "x");
    var resHeightInput = resGroup.add("edittext", undefined, "1080");
    resHeightInput.characters = 5;
    
    // Frame rate
    var fpsGroup = settingsGroup.add("group");
    fpsGroup.orientation = "row";
    fpsGroup.add("statictext", undefined, "Frame Rate:");
    var fpsInput = fpsGroup.add("edittext", undefined, "25");
    fpsInput.characters = 4;
    
    // Preview area
    var previewGroup = panel.add("group");
    previewGroup.orientation = "column";
    var previewText = previewGroup.add("statictext", undefined, "Select folder to preview cameras...");
    previewText.preferredSize.width = 400;
    
    // Buttons
    var buttonGroup = panel.add("group");
    buttonGroup.orientation = "row";
    var importButton = buttonGroup.add("button", undefined, "Import & Create Quilt");
    var cancelButton = buttonGroup.add("button", undefined, "Cancel");
    
    importButton.enabled = false;
    
    // Folder selection handler
    folderButton.onClick = function() {
        var folder = Folder.selectDialog("Select folder containing animation sequences");
        if (folder) {
            folderPath = folder;
            analyzeCameras(folder);
        }
    };
    
    // Analyze cameras in folder
    function analyzeCameras(folder) {
        var files = folder.getFiles("*.png");
        var cameras = {};
        var baseName = "";
        
        for (var i = 0; i < files.length; i++) {
            var fileName = files[i].name;
            // Match pattern: name_camera_frame.png
            var match = fileName.match(/^(.+)_(\d+)_(\d+)\.png$/);
            if (match) {
                baseName = match[1];
                var camera = parseInt(match[2]);
                var frame = parseInt(match[3]);
                
                if (!cameras[camera]) {
                    cameras[camera] = [];
                }
                cameras[camera].push(frame);
            }
        }
        
        var cameraList = [];
        for (var cam in cameras) {
            cameraList.push(parseInt(cam));
            cameras[cam].sort(function(a, b) { return a - b; });
        }
        cameraList.sort(function(a, b) { return a - b; });
        
        var previewInfo = "Found: " + cameraList.length + " cameras\\n";
        previewInfo += "Base name: " + baseName + "\\n";
        previewInfo += "Cameras: " + cameraList.join(", ") + "\\n";
        previewInfo += "Frame range: " + Math.min.apply(null, cameras[cameraList[0]]) + 
                      " - " + Math.max.apply(null, cameras[cameraList[0]]);
        
        previewText.text = previewInfo;
        importButton.enabled = cameraList.length > 0;
    }
    
    // Import and create quilt
    importButton.onClick = function() {
        if (!folderPath) {
            alert("Please select a folder first.");
            return;
        }
        
        var quiltWidth = parseInt(widthInput.text);
        var quiltHeight = parseInt(heightInput.text);
        var camWidth = parseInt(resWidthInput.text);
        var camHeight = parseInt(resHeightInput.text);
        var fps = parseFloat(fpsInput.text);
        
        if (isNaN(quiltWidth) || isNaN(quiltHeight) || isNaN(camWidth) || isNaN(camHeight) || isNaN(fps)) {
            alert("Please enter valid numbers for all settings.");
            return;
        }
        
        panel.close();
        createQuilt(folderPath, quiltWidth, quiltHeight, camWidth, camHeight, fps);
    };
    
    cancelButton.onClick = function() {
        panel.close();
    };
    
    function createQuilt(folder, qWidth, qHeight, camWidth, camHeight, fps) {
        app.beginUndoGroup("Create Multi-Camera Quilt");
        
        try {
            // Get all cameras
            var files = folder.getFiles("*.png");
            var cameras = {};
            var baseName = "";
            
            for (var i = 0; i < files.length; i++) {
                var fileName = files[i].name;
                var match = fileName.match(/^(.+)_(\d+)_(\d+)\.png$/);
                if (match) {
                    baseName = match[1];
                    var camera = parseInt(match[2]);
                    
                    if (!cameras[camera]) {
                        cameras[camera] = [];
                    }
                    cameras[camera].push(files[i]);
                }
            }
            
            var cameraList = [];
            for (var cam in cameras) {
                cameraList.push(parseInt(cam));
            }
            cameraList.sort(function(a, b) { return a - b; });
            
            // Import sequences
            var importedSequences = {};
            for (var c = 0; c < cameraList.length; c++) {
                var camNum = cameraList[c];
                var firstFile = null;
                
                // Find first frame for this camera
                for (var f = 0; f < cameras[camNum].length; f++) {
                    var fileName = cameras[camNum][f].name;
                    var match = fileName.match(/^(.+)_(\d+)_(\d+)\.png$/);
                    if (match) {
                        var frame = parseInt(match[3]);
                        if (!firstFile || frame < firstFileFrame) {
                            firstFile = cameras[camNum][f];
                            var firstFileFrame = frame;
                        }
                    }
                }
                
                if (firstFile) {
                    var importOptions = new ImportOptions(firstFile);
                    importOptions.sequence = true;
                    var sequence = app.project.importFile(importOptions);
                    sequence.name = baseName + "_Camera_" + String(camNum).padStart(2, '0');
                    importedSequences[camNum] = sequence;
                }
            }
            
            // Create quilt composition
            var compWidth = qWidth * camWidth;
            var compHeight = qHeight * camHeight;
            var comp = app.project.items.addComp(baseName + "_Quilt_" + qWidth + "x" + qHeight, 
                                                compWidth, compHeight, 1.0, 
                                                importedSequences[cameraList[0]].duration, fps);
            
            // Arrange cameras in quilt pattern
            var camIndex = 0;
            for (var row = 0; row < qHeight; row++) {
                for (var col = 0; col < qWidth; col++) {
                    if (camIndex < cameraList.length) {
                        var camNum = cameraList[camIndex];
                        var sequence = importedSequences[camNum];
                        
                        var layer = comp.layers.add(sequence);
                        layer.name = "Camera_" + String(camNum).padStart(2, '0');
                        
                        // Position: bottom-left is 0,0, so we need to flip Y
                        var x = col * camWidth + camWidth / 2;
                        var y = (qHeight - 1 - row) * camHeight + camHeight / 2;
                        
                        layer.property("Transform").property("Position").setValue([x, y]);
                        
                        camIndex++;
                    }
                }
            }
            
            alert("Quilt composition created successfully!\\n" + 
                  "Composition: " + comp.name + "\\n" +
                  "Resolution: " + compWidth + "x" + compHeight + "\\n" +
                  "Cameras imported: " + cameraList.length);
                  
        } catch (error) {
            alert("Error creating quilt: " + error.toString());
        }
        
        app.endUndoGroup();
    }
    
    // String padding function for older AE versions
    if (!String.prototype.padStart) {
        String.prototype.padStart = function(targetLength, padString) {
            targetLength = targetLength >> 0;
            padString = String(padString || ' ');
            if (this.length > targetLength) {
                return String(this);
            } else {
                targetLength = targetLength - this.length;
                if (targetLength > padString.length) {
                    padString += padString.repeat(targetLength / padString.length);
                }
                return padString.slice(0, targetLength) + String(this);
            }
        };
    }
    
    panel.show();
})();