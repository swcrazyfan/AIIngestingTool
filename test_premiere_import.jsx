// Test script for Premiere Pro import functionality
// Run this in ExtendScript Toolkit or Premiere Pro's ExtendScript console

// Test importing a file to project
function testImportToProject() {
    // Replace this path with a real video file on your system
    var testFilePath = "/path/to/your/test/video.mp4";
    
    try {
        $.writeln("Testing import to project...");
        
        if (!app.project) {
            alert("No project open");
            return false;
        }

        var file = new File(testFilePath);
        if (!file.exists) {
            alert("Test file not found: " + testFilePath);
            return false;
        }

        $.writeln("File exists, proceeding with import...");

        var importedItems = app.project.importFiles([testFilePath], false, app.project.rootItem, false);

        $.writeln("Import result type: " + typeof importedItems);
        $.writeln("Import result: " + importedItems);

        if (importedItems === false) {
            alert("Failed to import file to project.");
            return false;
        }

        $.writeln("Import successful!");
        return true;
    } catch (e) {
        $.writeln("Error: " + e.toString());
        alert("Error: " + e.toString());
        return false;
    }
}

// Test adding a file to timeline (assumes the file is already imported)
function testAddToTimeline() {
    try {
        $.writeln("Testing add to timeline...");
        
        if (!app.project) {
            alert("No project open");
            return false;
        }

        if (!app.project.activeSequence) {
            alert("No active sequence");
            return false;
        }

        if (app.project.activeSequence.videoTracks.numTracks === 0) {
            alert("No video tracks in sequence");
            return false;
        }

        // Get the first item in the project (assuming it exists)
        var rootItems = app.project.rootItem.children;
        if (rootItems.numItems === 0) {
            alert("No items in project to add to timeline");
            return false;
        }

        var videoItem = rootItems[0];
        var currentTime = app.project.activeSequence.getOutPoint();
        
        $.writeln("Current sequence out point: " + currentTime + " (type: " + typeof currentTime + ")");
        
        var insertTime = 0;
        if (typeof currentTime === 'string') {
            var numTime = parseFloat(currentTime);
            if (!isNaN(numTime)) {
                insertTime = numTime;
            }
        } else if (typeof currentTime === 'number') {
            insertTime = currentTime;
        }

        $.writeln("Inserting clip at time: " + insertTime);

        app.project.activeSequence.videoTracks[0].insertClip(videoItem, insertTime);
        
        $.writeln("Clip inserted successfully!");
        return true;
    } catch (e) {
        $.writeln("Error: " + e.toString());
        alert("Error: " + e.toString());
        return false;
    }
}

// Run the tests
$.writeln("=== Testing Premiere Pro Import Functions ===");

// Update this path to point to a real video file on your system
var testFile = "/Users/developer/Desktop/test_video.mp4";

// Test 1: Import to project
$.writeln("\n1. Testing import to project:");
testImportToProject();

// Test 2: Add to timeline (only if you have items in your project)
$.writeln("\n2. Testing add to timeline:");
testAddToTimeline();

$.writeln("\n=== Test Complete ==="); 