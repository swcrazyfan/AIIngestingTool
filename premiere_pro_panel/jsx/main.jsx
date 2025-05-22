/**
 * AI Video Ingest Tool - ExtendScript for Premiere Pro
 * Handles direct Premiere Pro integration and automation
 */

// Utility functions for safe file operations
function safeImportFile(filePath) {
    try {
        var file = new File(filePath);
        if (!file.exists) {
            return { success: false, error: "File not found: " + filePath };
        }
        
        var project = app.project;
        var imported = project.importFiles([filePath]);
        
        if (imported && imported.length > 0) {
            return { success: true, projectItem: imported[0] };
        } else {
            return { success: false, error: "Failed to import file" };
        }
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}

function addToTimelineAtCurrentPosition(projectItem) {
    try {
        var sequence = app.project.activeSequence;
        if (!sequence) {
            return { success: false, error: "No active sequence" };
        }
        
        // Get current playhead position
        var currentTime = sequence.getPlayerPosition();
        
        // Insert at current position on first available tracks
        var success = sequence.insertClip(projectItem, currentTime, 0, 0);
        
        if (success) {
            return { success: true, message: "Clip added to timeline" };
        } else {
            return { success: false, error: "Failed to insert clip" };
        }
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}

function addToTimelineAtEnd(projectItem) {
    try {
        var sequence = app.project.activeSequence;
        if (!sequence) {
            return { success: false, error: "No active sequence" };
        }
        
        // Find the end of the timeline
        var endTime = sequence.end;
        
        // Insert at end
        var success = sequence.insertClip(projectItem, endTime, 0, 0);
        
        if (success) {
            return { success: true, message: "Clip added to end of timeline" };
        } else {
            return { success: false, error: "Failed to insert clip at end" };
        }
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}

function createNewSequenceFromFile(filePath, sequenceName) {
    try {
        // Import the file first
        var importResult = safeImportFile(filePath);
        if (!importResult.success) {
            return importResult;
        }
        
        var projectItem = importResult.projectItem;
        
        // Create new sequence based on the clip's settings
        var project = app.project;
        
        // Get clip properties for sequence settings
        // This is simplified - in practice you'd want to match the clip's specs exactly
        var newSequence = project.newSequence(sequenceName || "New Sequence", null);
        
        if (newSequence) {
            // Add the clip to the new sequence
            newSequence.insertClip(projectItem, 0, 0, 0);
            
            return { 
                success: true, 
                sequence: newSequence,
                message: "New sequence created with clip" 
            };
        } else {
            return { success: false, error: "Failed to create sequence" };
        }
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}function batchImportFiles(filePaths) {
    try {
        var project = app.project;
        var results = {
            success: true,
            imported: [],
            failed: [],
            message: ""
        };
        
        for (var i = 0; i < filePaths.length; i++) {
            var filePath = filePaths[i];
            var file = new File(filePath);
            
            if (file.exists) {
                try {
                    var imported = project.importFiles([filePath]);
                    if (imported && imported.length > 0) {
                        results.imported.push({
                            path: filePath,
                            projectItem: imported[0]
                        });
                    } else {
                        results.failed.push({
                            path: filePath,
                            error: "Import failed"
                        });
                    }
                } catch (importError) {
                    results.failed.push({
                        path: filePath,
                        error: importError.toString()
                    });
                }
            } else {
                results.failed.push({
                    path: filePath,
                    error: "File not found"
                });
            }
        }
        
        results.message = "Imported " + results.imported.length + " files, " + 
                         results.failed.length + " failed";
        
        return results;
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}

function getSequenceInfo() {
    try {
        var sequence = app.project.activeSequence;
        if (!sequence) {
            return { success: false, error: "No active sequence" };
        }
        
        return {
            success: true,
            name: sequence.name,
            duration: sequence.end,
            frameRate: sequence.timebase,
            width: sequence.frameSizeHorizontal,
            height: sequence.frameSizeVertical,
            audioTracks: sequence.audioTracks.numTracks,
            videoTracks: sequence.videoTracks.numTracks
        };
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}

function getProjectInfo() {
    try {
        var project = app.project;
        
        return {
            success: true,
            name: project.name,
            path: project.path,
            sequences: project.sequences.numSequences,
            rootItems: project.rootItem.children.numItems
        };
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}

// Main functions called from the panel
function importAndAddToTimeline(filePath) {
    var importResult = safeImportFile(filePath);
    if (!importResult.success) {
        return JSON.stringify(importResult);
    }
    
    var timelineResult = addToTimelineAtCurrentPosition(importResult.projectItem);
    return JSON.stringify(timelineResult);
}

function importToProject(filePath) {
    var importResult = safeImportFile(filePath);
    return JSON.stringify(importResult);
}

function revealFileInFinder(filePath) {
    try {
        var file = new File(filePath);
        if (file.exists) {
            file.execute();
            return JSON.stringify({ success: true, message: "File revealed" });
        } else {
            return JSON.stringify({ success: false, error: "File not found" });
        }
    } catch (e) {
        return JSON.stringify({ success: false, error: e.toString() });
    }
}