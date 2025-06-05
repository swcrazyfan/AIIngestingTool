# Category-Based Library Implementation Plan

## Overview

This document outlines the implementation of a category-based library system for the AI Video Ingest Tool's Adobe Premiere Pro extension. The system will allow users to browse videos by category/subcategory and bulk import entire categories as folder structures into Premiere Pro.

## Current State Analysis

### What We Have
- **Database**: `content_category` field in the clips table storing categories like "Interview", "Tutorial", "Event", etc.
- **AI Analysis**: Categories are automatically assigned during video analysis
- **API**: Basic filtering capability exists but no dedicated category endpoints
- **Extension**: Single "Library" view showing all videos with search/filter

### What's Missing
- No hierarchical category structure (categories + subcategories)
- No API endpoints for category operations
- No UI for browsing by category
- No bulk import functionality for categories into Premiere Pro

## Proposed Solution

### Two-Page Architecture

1. **Library Page** (Category Browser)
   - Visual category cards/folders showing video counts
   - Hierarchical navigation (categories → subcategories → videos)
   - Bulk import button to add entire categories to Premiere Pro
   - Category-based organization

2. **Browse Page** (Enhanced Search)
   - Current search functionality retained
   - Added category filter dropdown
   - All existing filtering and sorting options

## Implementation Steps

### Phase 1: Backend API Development

#### 1.1 Database Schema Updates
No schema changes needed - we'll use the existing `content_category` field but parse it for hierarchy using "/" as a separator (e.g., "Tutorial/Programming", "Event/Conference").

#### 1.2 New API Endpoints

```python
# In video_ingest_tool/api/server.py

# GET /api/categories
# Returns all unique categories with video counts
# Response: {
#   "categories": [
#     {
#       "name": "Tutorial",
#       "count": 45,
#       "subcategories": [
#         {"name": "Programming", "count": 20, "full_path": "Tutorial/Programming"},
#         {"name": "Design", "count": 25, "full_path": "Tutorial/Design"}
#       ]
#     }
#   ]
# }

# GET /api/categories/{category}/clips
# Returns all clips in a specific category (supports hierarchical paths)
# Example: /api/categories/Tutorial%2FProgramming/clips
# Response: Standard clips list response

# GET /api/categories/{category}/tree
# Returns category with full hierarchy and clip IDs for bulk operations
# Response: {
#   "category": "Tutorial",
#   "total_clips": 45,
#   "structure": {
#     "Programming": {
#       "clips": ["clip_id_1", "clip_id_2"],
#       "subcategories": {}
#     }
#   }
# }
```

#### 1.3 Backend Implementation Tasks

1. **Create CategoryCommand class** in `video_ingest_tool/cli_commands/categories.py`
2. **Add category parsing logic** to extract hierarchical structure from `content_category` field
3. **Implement category aggregation** queries in DuckDB
4. **Add routes** to the Flask server
5. **Handle URL encoding** for category paths with slashes

### Phase 2: Extension Frontend Development

#### 2.1 Research Requirements

Before implementing the Premiere Pro integration:

1. **Research bolt-cep framework**:
   - Study the existing ppro.ts and ppro-utils.ts files
   - Understand CSInterface and ExtendScript communication
   - Review how the current `addVideoToTimeline` and `importVideoToProject` functions work

2. **Research Premiere Pro ExtendScript**:
   - Use Context7 or Adobe's documentation to understand:
     - ProjectItem structure and bin management
     - Creating nested bin structures programmatically
     - Batch importing files while maintaining organization
     - Error handling for missing files or failed imports

3. **Study existing patterns**:
   - How the extension currently handles file paths
   - The communication between React components and ExtendScript
   - Error handling and user feedback mechanisms

#### 2.2 New Components Structure

```
src/js/components/
├── LibraryView.tsx (new - main container for category view)
├── CategoryBrowser.tsx (new - category cards/navigation)
├── CategoryVideoList.tsx (new - videos within a category)
├── BrowseView.tsx (renamed from VideoLibrary.tsx)
└── VideoCard.tsx (existing - enhanced for both views)
```

#### 2.3 Frontend Implementation Tasks

1. **Update Navigation**:
   ```tsx
   // In main.tsx
   const [activeTab, setActiveTab] = useState<'library' | 'browse' | 'ingest'>('library');
   ```

2. **Create CategoryBrowser Component**:
   - Fetch categories from `/api/categories`
   - Display as cards with video counts
   - Handle navigation into subcategories
   - Show breadcrumb navigation

3. **Create Bulk Import Functionality**:
   ```typescript
   // In src/jsx/ppro/ppro.ts
   export const importCategoryToProject = (
     categoryName: string, 
     videoPaths: string[]
   ): boolean => {
     // Create bin structure matching category hierarchy
     // Import all videos maintaining organization
     // Return success/failure status
   };
   ```

4. **Enhance VideoCard Component**:
   - Add category display
   - Support both grid and list views
   - Maintain existing functionality

### Phase 3: ExtendScript Integration

#### 3.1 Premiere Pro Bin Management

```typescript
// New functions in ppro-utils.ts

export const createBinHierarchy = (
  rootItem: ProjectItem,
  path: string[]
): ProjectItem => {
  // Recursively create bin structure
  // Handle existing bins gracefully
};

export const importFilesToBin = (
  bin: ProjectItem,
  filePaths: string[]
): ProjectItem[] => {
  // Batch import with progress callback
  // Handle errors for individual files
};
```

#### 3.2 Progress Feedback

Implement progress tracking for bulk imports:
- Show progress modal during import
- Report success/failure for each file
- Allow cancellation of long operations

### Phase 4: Testing & Polish

1. **Test Cases**:
   - Empty categories
   - Large categories (100+ videos)
   - Nested categories (3+ levels deep)
   - Special characters in category names
   - Missing video files during import

2. **Performance Optimization**:
   - Implement virtual scrolling for large video lists
   - Cache category data client-side
   - Optimize thumbnail loading

3. **User Experience**:
   - Add loading states
   - Implement error boundaries
   - Add keyboard navigation
   - Include category search/filter

## Technical Considerations

### API Design Principles
- RESTful endpoints following existing patterns
- Consistent response format with success/error structure
- Proper HTTP status codes
- Support for pagination in category clip lists

### Frontend State Management
- Use React Query for API data caching
- Implement optimistic updates for UI responsiveness
- Handle connection loss gracefully

### Premiere Pro Integration
- Respect Premiere Pro's threading model
- Handle large file operations asynchronously
- Provide clear error messages for import failures
- Maintain undo capability where possible

## Development Workflow

1. **Start with API development** - implement and test endpoints
2. **Create mock data** for frontend development
3. **Build UI components** in isolation
4. **Integrate with real API**
5. **Implement Premiere Pro functions**
6. **End-to-end testing**
7. **Performance optimization**
8. **Documentation updates**

## Success Criteria

- Users can browse videos organized by category
- Categories support hierarchical organization
- Bulk import creates proper folder structure in Premiere Pro
- Performance remains smooth with 1000+ videos
- All existing functionality remains intact
- Clear error messages for all failure scenarios

## Future Enhancements

- Custom category assignment/editing
- Smart collections based on metadata
- Category-based export presets
- Saved category views/filters
- Category statistics and insights

## Notes for Implementation

1. **Start Small**: Begin with flat categories before adding hierarchy
2. **Preserve Compatibility**: Ensure existing API consumers continue to work
3. **Progressive Enhancement**: Show basic functionality first, add features iteratively
4. **User Feedback**: Include progress indicators for all long operations
5. **Error Recovery**: Always provide a way to retry failed operations

## Resources Needed

- Access to Context7 for Premiere Pro ExtendScript documentation
- Test project with diverse video categories
- Performance testing tools for large datasets
- User feedback from video editors using the tool

---

This implementation plan provides a clear roadmap for adding category-based library functionality while maintaining the tool's existing capabilities and ensuring a smooth user experience.
