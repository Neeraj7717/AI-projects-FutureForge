# Instagram Workflow Builder

A complete web application for Instagram comment-to-DM automation workflow builder with desktop layout (sidebar + preview) built with React, TypeScript, and Material-UI.

## Features

### 🎯 Desktop Layout
- **Sidebar**: 400px width with white background and workflow steps
- **Preview Area**: iPhone frame with Instagram post and DM previews
- **Responsive Design**: Fixed sidebar with flexible preview area
- **Real-time Updates**: Live preview as you configure the workflow

### 📱 Three-Step Workflow UI

#### Step 1: Post Selection
- Dropdown/list to select specific posts or reels from mock dataset
- Post cards with thumbnails, captions, and engagement metrics
- Real-time preview updates in iPhone frame

#### Step 2: Comment Trigger
- Input field for keyword entry (e.g., "Price")
- Keyword chip display with numbering
- Live highlighting in preview comments
- Helper text and examples for keyword usage

#### Step 3: DM Configuration
- DM message preview with character counter
- Textarea for message editing
- "Add A Link" functionality
- Instagram-style DM chat preview

### 🎨 Exact Styling Specifications
- **Colors**: Instagram's exact color palette (#FAFAFA, #FFFFFF, #262626, #8E8E8E)
- **Typography**: Roboto font family
- **Buttons**: Linear gradient styling (#4CB5F9 to #B32EFF)
- **Components**: Material-UI components with Instagram styling

### 🔄 Interactive Features
- **Post Selection**: Card-based post selection with thumbnails
- **Keyword Management**: Input field with live preview highlighting
- **DM Configuration**: Real-time character counting and chat preview
- **Navigation**: Step validation and smooth transitions
- **Go Live**: Button in preview area with Instagram styling

## Getting Started

### Prerequisites
- Node.js (v14 or higher)
- npm or yarn

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd instagram-workflow-builder
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

4. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

### Build for Production

```bash
npm run build
```

## Project Structure

```
src/
├── components/
│   ├── InstagramWorkflowBuilder.tsx  # Main component with desktop layout
│   ├── Sidebar.tsx                   # Left sidebar with workflow steps
│   ├── Preview.tsx                   # Right preview area with iPhone frame
│   └── data/
│       └── mockData.ts               # Mock Instagram posts data
├── App.tsx                          # App entry point
└── index.tsx                        # React root
```

## Technologies Used

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Material-UI** - Component library
- **Emotion** - Styled components
- **React Scripts** - Build tooling

## Design System

### Colors
- Background: `#FAFAFA`
- Cards: `#FFFFFF` with `#DBDBDB` border
- Primary Text: `#262626`
- Secondary Text: `#8E8E8E`
- Primary Button: Linear gradient `#4CB5F9` to `#B32EFF`
- Live Button: Linear gradient `#FF6B6B` to `#FF8E53`

### Typography
- Font Family: Roboto
- H1: 24px Semibold
- H2: 20px Semibold
- Body: 16px Regular
- Caption: 14px Regular

### Spacing
- Container padding: 16px
- Component spacing: 12px, 16px, 20px, 24px
- Border radius: 8px (cards), 32px (device frame)

## Mobile Interactions

### Gestures
- **Swipe-down-to-close**: Bottom sheet dismissal
- **Tap targets**: 44px minimum height
- **Momentum scrolling**: Native iOS feel

### Responsive Design
- Fixed 400px sidebar width
- Flexible preview area with iPhone frame
- Desktop-optimized layout

## Future Enhancements

- [ ] Real Instagram API integration
- [ ] Workflow templates
- [ ] Analytics dashboard
- [ ] Multi-language support
- [ ] Dark mode support
- [ ] Advanced keyword matching
- [ ] A/B testing for DM messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Acknowledgments

- Instagram for the original design inspiration
- Material-UI for the component library
- SF Pro Display font family 