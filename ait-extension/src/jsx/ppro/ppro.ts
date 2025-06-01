// ExtendScript functions for Premiere Pro integration

export const selectDirectory = (): string | null => {
  try {
    const folder = Folder.selectDialog("Select video directory");
    if (folder) {
      return folder.fsName;
    }
  } catch (e: any) {
    // Silently log the error but don't show alerts
    $.writeln("Error in selectDirectory: " + e.toString());
  }
  return null;
};

export const addVideoToTimeline = (filePath: string): boolean => {
  try {
    let cleanFilePath = filePath;
    try {
      // Attempt to parse if it's a JSON-stringified string
      const parsed = JSON.parse(filePath);
      if (typeof parsed === 'string') {
        cleanFilePath = parsed;
      }
    } catch (e: any) {
      // Not a JSON string, use as is
      // Log parsing error for debugging if needed
      // app.setSDKEventMessage("JSON.parse error in addVideoToTimeline: " + e.toString(), "error");
    }

    const project = app.project;
    if (!project) {
      alert("No project open");
      return false;
    }

    // Import the file
    const importedItems: ProjectItem[] | boolean = project.importFiles([cleanFilePath], true, project.rootItem, false);

    if (importedItems === false) {
      alert("Failed to import file for timeline (importFiles returned false).");
      return false;
    }

    if (importedItems === true) {
      // Import was acknowledged, but no direct ProjectItem array returned.
      // This can happen with suppressUI=true. We can't add to timeline without a specific item.
      alert("File import acknowledged, but item not directly available to add to timeline. Please find it in the Project panel.");
      return false; // Or true if partial success is acceptable, but for adding to timeline, it's a failure.
    }

    // At this point, importedItems should be ProjectItem[]
    const itemsArray = importedItems as ProjectItem[]; // Explicit cast
    if (itemsArray.length === 0) {
      alert("Failed to import file for timeline (no items imported).");
      return false;
    }

    const videoItem: ProjectItem = itemsArray[0];
    if (!videoItem) {
      // This case should ideally be caught by importedItems.length === 0, but as a safeguard:
      alert("Failed to get a valid video item after import.");
      return false;
    }

    const targetSequence = project.activeSequence;
    if (!targetSequence) {
      alert("No active sequence");
      return false;
    }

    // Add video to the first video track
    // Ensure there's at least one video track
    if (targetSequence.videoTracks.numTracks === 0) {
        // Attempting to insert into videoTracks[0] will fail if no tracks exist.
        // Premiere Pro might auto-create a track, or it might error.
        // For simplicity, we'll let it try and error if no tracks exist and none are auto-created.
        // A more robust solution would be to explicitly add a track if numTracks is 0:
        // try { targetSequence.videoTracks.add(); } catch(e) { alert("Failed to add video track."); return false; }
        alert("No video tracks in the sequence. Please add a video track.");
        return false;
    }
    // targetSequence.getOutPoint() returns a timecode string. Convert to seconds.
    const outPointTimecode: string = targetSequence.getOutPoint();
    const outPointInSeconds: number = (app.project as any).timeToSeconds(outPointTimecode);

    if (typeof outPointInSeconds === 'number' && !isNaN(outPointInSeconds)) {
      targetSequence.videoTracks[0].insertClip(videoItem, outPointInSeconds);
    } else {
      alert("Could not determine valid out point (seconds) for sequence. Attempting to insert at time 0.");
      targetSequence.videoTracks[0].insertClip(videoItem, 0);
    }
    return true;
  } catch (e: any) {
    alert("Error in addVideoToTimeline: " + e.toString());
    return false;
  }
};

export const importVideoToProject = (filePath: string): boolean => {
  try {
    let cleanFilePath = filePath;
    try {
      // Attempt to parse if it's a JSON-stringified string
      const parsed = JSON.parse(filePath);
      if (typeof parsed === 'string') {
        cleanFilePath = parsed;
      }
    } catch (e: any) {
      // Not a JSON string, use as is
      // Log parsing error for debugging if needed
      // app.setSDKEventMessage("JSON.parse error in importVideoToProject: " + e.toString(), "error");
    }

    const project = app.project;
    if (!project) {
      alert("No project open");
      return false;
    }

    // Import the file to project panel
    const importedItems: ProjectItem[] | boolean = project.importFiles([cleanFilePath], true, project.rootItem, false);

    if (importedItems === false) {
      alert("Failed to import file to project (importFiles returned false).");
      return false;
    }

    if (importedItems === true) {
      // Import was acknowledged. This is a success for just importing to project.
      return true;
    }

    // At this point, importedItems should be ProjectItem[]
    const itemsArrayResult = importedItems as ProjectItem[]; // Explicit cast
    if (itemsArrayResult.length === 0) {
      alert("Failed to import file to project (no items imported).");
      return false;
    }

    // If we have an array with items, it's a success.
    return true;
  } catch (e: any) {
    alert("Error in importVideoToProject: " + e.toString());
    return false;
  }
};

export const revealInFinder = (filePath: string): boolean => {
  try {
    const file = new File(filePath);
    if (file.exists) {
      file.parent.execute();
      return true;
    } else {
      alert("File not found: " + filePath);
      return false;
    }
  } catch (e: any) {
    alert("Error revealing file: " + e.toString());
    return false;
  }
};

export const getProjectName = (): string => {
  try {
    if (app.project) {
      return app.project.name;
    }
    return "No project open";
  } catch (e: any) {
    return "Error getting project name: " + e.toString();
  }
};

export const getSequenceName = (): string => {
  try {
    if (app.project && app.project.activeSequence) {
      return app.project.activeSequence.name;
    }
    return "No active sequence";
  } catch (e: any) {
    return "Error getting sequence name: " + e.toString();
  }
};

// Example function to demonstrate getting some project stats
export const getProjectStats = (): string => {
  try {
    if (!app.project) {
      return "No project open.";
    }
    const numSequences = app.project.sequences.numSequences;
    const numRootItems = app.project.rootItem.children.numItems;
    return (
      "Project: " +
      app.project.name +
      "\nSequences: " +
      numSequences +
      "\nRoot Items: " +
      numRootItems
    );
  } catch (e: any) {
    return "Error getting project stats: " + e.toString();
  }
};