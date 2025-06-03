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
      const parsed = JSON.parse(filePath);
      if (typeof parsed === 'string') {
        cleanFilePath = parsed;
      }
    } catch (e: any) {
      // Not a JSON string, use as is
    }

    const project = app.project;
    if (!project) {
      return false;
    }

    const targetSequence = project.activeSequence;
    if (!targetSequence) {
      return false;
    }

    if (targetSequence.videoTracks.numTracks === 0) {
      return false;
    }

    const importedItems: ProjectItem[] | boolean = project.importFiles([cleanFilePath], true, project.rootItem, false);

    if (importedItems === false) {
      return false;
    }

    let videoItem: ProjectItem | null = null;

    if (importedItems === true) {
      const rootItems = project.rootItem.children;
      for (let i = rootItems.numItems - 1; i >= 0; i--) {
        const item = rootItems[i];
        if (item && item.getMediaPath() === cleanFilePath) {
          videoItem = item;
          break;
        }
      }
      
      if (!videoItem) {
        return false;
      }
    } else {
      const itemsArray = importedItems as ProjectItem[];
      if (itemsArray.length === 0) {
        return false;
      }
      videoItem = itemsArray[0];
    }

    if (!videoItem) {
      return false;
    }

    const currentTime = targetSequence.getOutPoint();
    let insertTime = 0;
    if (typeof currentTime === 'string') {
      const numTime = parseFloat(currentTime);
      if (!isNaN(numTime)) {
        insertTime = numTime;
      }
    } else if (typeof currentTime === 'number') {
      insertTime = currentTime;
    }

    targetSequence.videoTracks[0].insertClip(videoItem, insertTime);
    
    return true;
  } catch (e: any) {
    return false;
  }
};

export const importVideoToProject = (filePath: string): boolean => {
  try {
    let cleanFilePath = filePath;
    try {
      const parsed = JSON.parse(filePath);
      if (typeof parsed === 'string') {
        cleanFilePath = parsed;
      }
    } catch (e: any) {
      // Not a JSON string, use as is
    }

    const project = app.project;
    if (!project) {
      return false;
    }

    const file = new File(cleanFilePath);
    if (!file.exists) {
      return false;
    }

    const importedItems: ProjectItem[] | boolean = project.importFiles([cleanFilePath], false, project.rootItem, false);

    if (importedItems === false) {
      return false;
    }

    return true;
  } catch (e: any) {
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