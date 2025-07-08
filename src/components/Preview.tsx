import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Avatar,
  IconButton,
  styled,
  Dialog,
  DialogContent,
  DialogActions,
  Drawer,
  TextField,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Divider,
} from '@mui/material';
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import SendIcon from '@mui/icons-material/Send';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import HomeIcon from '@mui/icons-material/Home';
import SearchIcon from '@mui/icons-material/Search';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import PersonIcon from '@mui/icons-material/Person';
import CloseIcon from '@mui/icons-material/Close';

const PreviewWrapper = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '24px',
});

const PreviewTitle = styled(Typography)({
  fontSize: '24px',
  fontWeight: 600,
  color: '#262626',
  textAlign: 'center',
  marginBottom: '8px',
});

const PreviewSubtitle = styled(Typography)({
  fontSize: '16px',
  color: '#8E8E8E',
  textAlign: 'center',
  marginBottom: '24px',
});

const PhoneFrame = styled(Box)({
  width: '350px',
  height: '600px',
  backgroundColor: '#000',
  borderRadius: '40px',
  padding: '8px',
  position: 'relative',
  boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
});

const Screen = styled(Box)({
  width: '100%',
  height: '100%',
  backgroundColor: '#FFFFFF',
  borderRadius: '32px',
  overflow: 'hidden',
  position: 'relative',
  display: 'flex',
  flexDirection: 'column',
});

const StatusBar = styled(Box)({
  height: '44px',
  backgroundColor: '#FFFFFF',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '0 20px',
  fontSize: '14px',
  fontWeight: 600,
  color: '#000',
  borderBottom: '1px solid #DBDBDB',
});

const GoLiveButton = styled(Button)({
  position: 'absolute',
  top: '16px',
  right: '16px',
  zIndex: 10,
  backgroundColor: '#FFFFFF',
  color: '#FF6B6B',
  border: '1px solid #FF6B6B',
  borderRadius: '20px',
  padding: '8px 16px',
  fontSize: '14px',
  fontWeight: 600,
  textTransform: 'none',
  '&:hover': {
    backgroundColor: '#FF6B6B',
    color: '#FFFFFF',
  },
});

const PostContainer = styled(Box)({
  flex: 1,
  backgroundColor: '#FFFFFF',
  overflow: 'auto', // Changed from 'hidden' to 'auto' to allow scrolling
  paddingBottom: '80px', // Increased padding to ensure content is not hidden
});

const PostHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 16px',
  borderBottom: '1px solid #DBDBDB',
});

const UserInfo = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
});

const Username = styled(Typography)({
  fontSize: '14px',
  fontWeight: 600,
  color: '#262626',
});

const PostImage = styled('img')({
  width: '100%',
  aspectRatio: '1',
  objectFit: 'cover',
  backgroundColor: '#F0F0F0',
  transition: 'opacity 0.3s ease',
  '&:hover': {
    opacity: 0.9,
  },
});

const PostActions = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '16px',
  padding: '12px 16px',
});

const ActionIcon = styled(IconButton)({
  color: '#262626',
  padding: '4px',
  '&:hover': {
    backgroundColor: 'transparent',
  },
});

const Caption = styled(Box)({
  padding: '0 16px 12px',
  fontSize: '14px',
  color: '#262626',
  lineHeight: 1.4,
});

const CommentSection = styled(Box)({
  padding: '0 16px 12px',
  borderTop: '1px solid #DBDBDB',
});

const Comment = styled(Box)<{ highlighted?: boolean }>(({ highlighted }) => ({
  display: 'flex',
  alignItems: 'flex-start',
  gap: '8px',
  marginBottom: '8px',
  padding: '8px',
  borderRadius: '8px',
  backgroundColor: highlighted ? '#FFF3CD' : 'transparent',
  border: highlighted ? '1px solid #FFEAA7' : 'none',
}));

const CommentUsername = styled(Typography)({
  fontSize: '14px',
  fontWeight: 600,
  color: '#262626',
});

const CommentText = styled(Typography)({
  fontSize: '14px',
  color: '#262626',
});

const DMContainer = styled(Box)({
  flex: 1,
  backgroundColor: '#262626',
  display: 'flex',
  flexDirection: 'column',
  paddingBottom: '80px', // Increased padding to ensure content is not hidden
});

const DMHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '12px 16px',
  backgroundColor: '#262626',
  borderBottom: '1px solid #404040',
});

const DMContent = styled(Box)({
  flex: 1,
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-end',
});

const DMMessage = styled(Box)({
  alignSelf: 'flex-end',
  backgroundColor: '#0095F6',
  color: '#FFFFFF',
  padding: '12px 16px',
  borderRadius: '18px',
  maxWidth: '80%',
  fontSize: '14px',
  lineHeight: 1.4,
  marginBottom: '8px',
  whiteSpace: 'pre-wrap',
});

const LivePopup = styled(Dialog)({
  '& .MuiDialog-paper': {
    borderRadius: '16px',
    padding: '24px',
    maxWidth: '400px',
    textAlign: 'center',
  },
});

const LivePopupContent = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '16px',
});

const LiveIcon = styled(Box)({
  width: '64px',
  height: '64px',
  borderRadius: '50%',
  backgroundColor: '#4CAF50',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: '#FFFFFF',
  fontSize: '32px',
});

const LiveTitle = styled(Typography)({
  fontSize: '24px',
  fontWeight: 600,
  color: '#262626',
});

const LiveMessage = styled(Typography)({
  fontSize: '16px',
  color: '#8E8E8E',
  lineHeight: 1.5,
});

const LiveButton = styled(Button)({
  backgroundColor: '#0095F6',
  color: '#FFFFFF',
  borderRadius: '8px',
  padding: '12px 24px',
  fontSize: '16px',
  fontWeight: 600,
  textTransform: 'none',
  '&:hover': {
    backgroundColor: '#0081D6',
  },
});

const BottomNavigation = styled(Box)({
  position: 'absolute',
  bottom: 0,
  left: 0,
  right: 0,
  height: '60px',
  backgroundColor: '#FFFFFF',
  borderTop: '1px solid #DBDBDB',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-around',
  padding: '0 16px',
});

const NavIcon = styled(IconButton)<{ active?: boolean }>(({ active }) => ({
  color: active ? '#262626' : '#8E8E8E',
  padding: '8px',
  borderRadius: '8px',
  '&:hover': {
    backgroundColor: 'transparent',
  },
  '& .MuiSvgIcon-root': {
    fontSize: '24px',
  },
}));

const CommentDrawer = styled(Drawer)({
  '& .MuiDrawer-paper': {
    height: '50%',
    borderTopLeftRadius: '16px',
    borderTopRightRadius: '16px',
    backgroundColor: '#FFFFFF',
  },
});

const CommentDrawerHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '16px',
  borderBottom: '1px solid #DBDBDB',
});

const CommentDrawerTitle = styled(Typography)({
  fontSize: '16px',
  fontWeight: 600,
  color: '#262626',
});

const CommentDrawerContent = styled(Box)({
  flex: 1,
  overflowY: 'auto',
  padding: '16px',
});

const CommentInputContainer = styled(Box)({
  padding: '16px',
  borderTop: '1px solid #DBDBDB',
  backgroundColor: '#FFFFFF',
});

const CommentInput = styled(TextField)({
  '& .MuiOutlinedInput-root': {
    borderRadius: '20px',
    backgroundColor: '#F8F9FA',
    '& fieldset': {
      border: 'none',
    },
    '&:hover fieldset': {
      border: 'none',
    },
    '&.Mui-focused fieldset': {
      border: 'none',
    },
  },
  '& .MuiInputBase-input': {
    padding: '12px 16px',
    fontSize: '14px',
  },
});

const EmptyState = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  color: '#8E8E8E',
  textAlign: 'center',
  padding: '40px 20px',
});

interface PreviewProps {
  step: number;
  selectedPost: any;
  keyword: string;
  dmMessage: string;
  onGoLive: () => void;
}

const Preview: React.FC<PreviewProps> = ({
  step,
  selectedPost,
  keyword,
  dmMessage,
  onGoLive,
}) => {
  const [livePopupOpen, setLivePopupOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('home');
  const [commentDrawerOpen, setCommentDrawerOpen] = useState(false);

  const getCurrentTime = () => {
    const now = new Date();
    return now.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const isHighlighted = (text: string): boolean => {
    return Boolean(keyword && text.toLowerCase().includes(keyword.toLowerCase()));
  };

  const handleGoLive = () => {
    setLivePopupOpen(true);
    onGoLive();
  };

  const handleCloseLivePopup = () => {
    setLivePopupOpen(false);
  };

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
  };

  const handleCommentClick = () => {
    setCommentDrawerOpen(true);
  };

  const handleCommentClose = () => {
    setCommentDrawerOpen(false);
  };

  const renderPostPreview = () => (
    <PostContainer>
      <PostHeader>
        <UserInfo>
          <Avatar sx={{ width: 32, height: 32 }}>U</Avatar>
          <Username>user123</Username>
        </UserInfo>
        <IconButton size="small">
          <MoreVertIcon />
        </IconButton>
      </PostHeader>
      
      <Box sx={{ position: 'relative' }}>
        <PostImage
          src={selectedPost?.image || 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=600&h=600&fit=crop&crop=center'}
          alt={selectedPost?.caption || 'Instagram post'}
        />
        {selectedPost?.type === 'reel' && (
          <Box
            sx={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              backgroundColor: 'rgba(0, 0, 0, 0.7)',
              color: '#FFFFFF',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            REEL
          </Box>
        )}
      </Box>
      
      <PostActions>
        <ActionIcon>
          <FavoriteBorderIcon />
        </ActionIcon>
        <ActionIcon onClick={handleCommentClick}>
          <ChatBubbleOutlineIcon />
        </ActionIcon>
        <ActionIcon>
          <SendIcon />
        </ActionIcon>
        <Box sx={{ marginLeft: 'auto' }}>
          <ActionIcon>
            <BookmarkBorderIcon />
          </ActionIcon>
        </Box>
      </PostActions>
      
      <Caption>
        <Username>user123</Username> {selectedPost?.caption || 'Beautiful sunset views! 🌅'}
      </Caption>
      
      <CommentSection>
        {keyword && (
          <Comment highlighted={isHighlighted('Price')}>
            <CommentUsername>traveler22</CommentUsername>
            <CommentText>{keyword}?</CommentText>
          </Comment>
        )}
        <Comment>
          <CommentUsername>user456</CommentUsername>
          <CommentText>Amazing shot!</CommentText>
        </Comment>
        <Typography 
          variant="body2" 
          color="text.secondary" 
          sx={{ cursor: 'pointer' }}
          onClick={handleCommentClick}
        >
          View all 24 comments
        </Typography>
      </CommentSection>
    </PostContainer>
  );

  const renderDMPreview = () => (
    <DMContainer>
      <DMHeader>
        <Avatar sx={{ width: 32, height: 32, backgroundColor: '#0095F6' }}>U</Avatar>
        <Username sx={{ color: '#FFFFFF' }}>user123</Username>
      </DMHeader>
      
      <DMContent>
        {dmMessage && (
          <DMMessage>
            {dmMessage}
          </DMMessage>
        )}
      </DMContent>
    </DMContainer>
  );

  const renderEmptyState = () => (
    <EmptyState>
      <Typography variant="h6" sx={{ marginBottom: '8px' }}>
        Instagram Preview
      </Typography>
      <Typography variant="body2">
        {step === 1 && 'Select a post to see the preview'}
        {step === 2 && 'Enter a keyword to see comment highlighting'}
        {step === 3 && 'Enter a DM message to see the preview'}
      </Typography>
    </EmptyState>
  );

  const renderPreview = () => {
    if (step === 3) {
      return renderDMPreview();
    }
    
    if (selectedPost) {
      return renderPostPreview();
    }
    
    return renderEmptyState();
  };

  const getPreviewTitle = () => {
    switch (step) {
      case 1:
        return 'Post Preview';
      case 2:
        return 'Comment Preview';
      case 3:
        return 'DM Preview';
      default:
        return 'Instagram Preview';
    }
  };

  const getPreviewSubtitle = () => {
    switch (step) {
      case 1:
        return 'See how your selected post will appear';
      case 2:
        return 'Preview comments with keyword highlighting';
      case 3:
        return 'Preview your automated DM response';
      default:
        return 'Select options to see the preview';
    }
  };

  return (
    <PreviewWrapper>
      <Box>
        <PreviewTitle>{getPreviewTitle()}</PreviewTitle>
        <PreviewSubtitle>{getPreviewSubtitle()}</PreviewSubtitle>
      </Box>
      
      <PhoneFrame>
        <Screen>
          <StatusBar>
            <span>{getCurrentTime()}</span>
            <span>●●●●●</span>
          </StatusBar>
          
          {step === 3 && (
            <GoLiveButton onClick={handleGoLive} startIcon={<PlayArrowIcon />}>
              Go Live
            </GoLiveButton>
          )}
          
          {renderPreview()}
          
          {/* Bottom Navigation */}
          <BottomNavigation>
            <NavIcon 
              active={activeTab === 'home'} 
              onClick={() => handleTabChange('home')}
            >
              <HomeIcon />
            </NavIcon>
            <NavIcon 
              active={activeTab === 'search'} 
              onClick={() => handleTabChange('search')}
            >
              <SearchIcon />
            </NavIcon>
            <NavIcon 
              active={activeTab === 'reels'} 
              onClick={() => handleTabChange('reels')}
            >
              <VideoLibraryIcon />
            </NavIcon>
            <NavIcon 
              active={activeTab === 'profile'} 
              onClick={() => handleTabChange('profile')}
            >
              <PersonIcon />
            </NavIcon>
          </BottomNavigation>
        </Screen>
      </PhoneFrame>

      {/* Comment Drawer */}
      <CommentDrawer
        anchor="bottom"
        open={commentDrawerOpen}
        onClose={handleCommentClose}
        PaperProps={{
          sx: {
            height: '50%',
            borderTopLeftRadius: '16px',
            borderTopRightRadius: '16px',
          }
        }}
      >
        <CommentDrawerHeader>
          <CommentDrawerTitle>Comments</CommentDrawerTitle>
          <IconButton onClick={handleCommentClose} size="small">
            <CloseIcon />
          </IconButton>
        </CommentDrawerHeader>
        
        <CommentDrawerContent>
          <List>
            {keyword && (
              <ListItem alignItems="flex-start" sx={{ padding: '8px 0' }}>
                <ListItemAvatar>
                  <Avatar sx={{ width: 32, height: 32, fontSize: '12px' }}>T</Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '14px' }}>
                        traveler22
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        2h
                      </Typography>
                    </Box>
                  }
                  secondary={
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        fontSize: '14px',
                        backgroundColor: '#FFF3CD',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        marginTop: '4px'
                      }}
                    >
                      {keyword}?
                    </Typography>
                  }
                />
              </ListItem>
            )}
            
            <ListItem alignItems="flex-start" sx={{ padding: '8px 0' }}>
              <ListItemAvatar>
                <Avatar sx={{ width: 32, height: 32, fontSize: '12px' }}>U</Avatar>
              </ListItemAvatar>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '14px' }}>
                      user456
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      1h
                    </Typography>
                  </Box>
                }
                secondary={
                  <Typography variant="body2" sx={{ fontSize: '14px', marginTop: '4px' }}>
                    Amazing shot!
                  </Typography>
                }
              />
            </ListItem>
            
            <ListItem alignItems="flex-start" sx={{ padding: '8px 0' }}>
              <ListItemAvatar>
                <Avatar sx={{ width: 32, height: 32, fontSize: '12px' }}>P</Avatar>
              </ListItemAvatar>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '14px' }}>
                      photographer99
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      30m
                    </Typography>
                  </Box>
                }
                secondary={
                  <Typography variant="body2" sx={{ fontSize: '14px', marginTop: '4px' }}>
                    Love the composition! 📸
                  </Typography>
                }
              />
            </ListItem>
          </List>
        </CommentDrawerContent>
        
        <CommentInputContainer>
          <CommentInput
            fullWidth
            placeholder="Add a comment..."
            variant="outlined"
            size="small"
          />
        </CommentInputContainer>
      </CommentDrawer>

      {/* Live Popup */}
      <LivePopup
        open={livePopupOpen}
        onClose={handleCloseLivePopup}
        maxWidth="sm"
        fullWidth
      >
        <DialogContent>
          <LivePopupContent>
            <LiveIcon>
              <CheckCircleIcon sx={{ fontSize: '32px' }} />
            </LiveIcon>
            <LiveTitle>Workflow is Live! 🎉</LiveTitle>
            <LiveMessage>
              Your Instagram automation is now active. When someone comments "{keyword}" on your post, 
              they will automatically receive your DM message.
            </LiveMessage>
          </LivePopupContent>
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', padding: '0 24px 24px' }}>
          <LiveButton onClick={handleCloseLivePopup}>
            Got it!
          </LiveButton>
        </DialogActions>
      </LivePopup>
    </PreviewWrapper>
  );
};

export default Preview; 