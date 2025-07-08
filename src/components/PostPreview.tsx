import React from 'react';
import { Box, styled, Drawer, IconButton, Avatar } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import SendIcon from '@mui/icons-material/Send';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import MoreVertIcon from '@mui/icons-material/MoreVert';

const BottomSheet = styled(Drawer)({
  '& .MuiDrawer-paper': {
    height: '80%',
    borderTopLeftRadius: '16px',
    borderTopRightRadius: '16px',
    backgroundColor: '#FFFFFF',
  },
});

const SheetHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '16px',
  borderBottom: '1px solid #DBDBDB',
});

const SheetTitle = styled(Box)({
  fontSize: '16px',
  fontWeight: 600,
  color: '#262626',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const PostContainer = styled(Box)({
  padding: '16px',
  backgroundColor: '#FFFFFF',
});

const PostHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: '12px',
});

const UserInfo = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
});

const Username = styled(Box)({
  fontSize: '14px',
  fontWeight: 600,
  color: '#262626',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const PostImage = styled(Box)({
  width: '100%',
  height: '200px',
  backgroundColor: '#F0F0F0',
  borderRadius: '8px',
  marginBottom: '12px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '14px',
  color: '#8E8E8E',
  backgroundImage: 'linear-gradient(45deg, #f0f0f0 25%, transparent 25%), linear-gradient(-45deg, #f0f0f0 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #f0f0f0 75%), linear-gradient(-45deg, transparent 75%, #f0f0f0 75%)',
  backgroundSize: '20px 20px',
  backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
});

const PostActions = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '16px',
  marginBottom: '12px',
});

const ActionIcon = styled(IconButton)({
  color: '#262626',
  padding: '4px',
  '&:hover': {
    backgroundColor: 'transparent',
  },
});

const Caption = styled(Box)({
  fontSize: '14px',
  color: '#262626',
  marginBottom: '12px',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
  lineHeight: 1.4,
});

const CommentSection = styled(Box)({
  borderTop: '1px solid #DBDBDB',
  paddingTop: '12px',
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

const CommentUsername = styled(Box)({
  fontSize: '14px',
  fontWeight: 600,
  color: '#262626',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const CommentText = styled(Box)({
  fontSize: '14px',
  color: '#262626',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const ViewAllComments = styled(Box)({
  fontSize: '14px',
  color: '#8E8E8E',
  cursor: 'pointer',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
  '&:hover': {
    color: '#262626',
  },
});

interface PostPreviewProps {
  open: boolean;
  onClose: () => void;
  keywords: string[];
}

const PostPreview: React.FC<PostPreviewProps> = ({ open, onClose, keywords }) => {
  const isHighlighted = (text: string) => {
    return keywords.some(keyword => 
      text.toLowerCase().includes(keyword.toLowerCase())
    );
  };

  return (
    <BottomSheet
      anchor="bottom"
      open={open}
      onClose={onClose}
    >
      <SheetHeader>
        <SheetTitle>Select Post</SheetTitle>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </SheetHeader>
      
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
        
        <PostImage>
          Travel Destination
        </PostImage>
        
        <PostActions>
          <ActionIcon>
            <FavoriteBorderIcon />
          </ActionIcon>
          <ActionIcon>
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
          <Username component="span">user123</Username> Beautiful sunset views! 🌅
        </Caption>
        
        <CommentSection>
          <Comment highlighted={isHighlighted('Price')}>
            <CommentUsername>traveler22</CommentUsername>
            <CommentText>Price?</CommentText>
          </Comment>
          <Comment>
            <CommentUsername>user456</CommentUsername>
            <CommentText>Amazing shot!</CommentText>
          </Comment>
          <ViewAllComments>View all 24 comments</ViewAllComments>
        </CommentSection>
      </PostContainer>
    </BottomSheet>
  );
};

export default PostPreview; 