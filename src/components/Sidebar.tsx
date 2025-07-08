import React, { useState } from 'react';
import {
  Box,
  Typography,
  Radio,
  RadioGroup,
  FormControlLabel,
  TextField,
  Button,
  Card,
  CardContent,
  Grid,
  Chip,
  styled,
  Dialog,
  DialogContent,
  DialogActions,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

const SidebarHeader = styled(Box)({
  padding: '20px 24px',
  backgroundColor: '#FAFAFA',
  borderBottom: '1px solid #DBDBDB',
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
});

const SidebarTitle = styled(Typography)({
  fontSize: '18px',
  fontWeight: 600,
  color: '#262626',
});

const StepIndicator = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  marginLeft: 'auto',
});

const StepDot = styled(Box)<{ active?: boolean; completed?: boolean }>(({ active, completed }) => ({
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  backgroundColor: completed ? '#0095F6' : active ? '#0095F6' : '#DBDBDB',
  transition: 'all 0.3s ease',
}));

const SidebarContainer = styled(Box)({
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
});

const SidebarContent = styled(Box)({
  padding: '24px',
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  overflowY: 'auto',
});

const StepContainer = styled(Box)({
  marginBottom: '32px',
});

const StepTitle = styled(Typography)({
  fontSize: '24px',
  fontWeight: 600,
  color: '#262626',
  marginBottom: '20px',
});

const RadioOption = styled(FormControlLabel)({
  margin: '12px 0',
  alignItems: 'flex-start',
  '& .MuiFormControlLabel-label': {
    fontSize: '16px',
    color: '#262626',
    lineHeight: 1.4,
    marginLeft: '8px',
  },
  '& .MuiRadio-root': {
    color: '#DBDBDB',
    '&.Mui-checked': {
      color: '#0095F6',
    },
  },
});

const PostCard = styled(Card)<{ selected?: boolean }>(({ selected }) => ({
  cursor: 'pointer',
  border: selected ? '2px solid #0095F6' : '1px solid #DBDBDB',
  borderRadius: '8px',
  marginBottom: '12px',
  transition: 'all 0.2s ease',
  '&:hover': {
    borderColor: selected ? '#0095F6' : '#262626',
  },
}));

const PostThumbnail = styled('img')({
  width: '100%',
  height: '120px',
  objectFit: 'cover',
  borderRadius: '8px',
  border: '1px solid #DBDBDB',
});

const KeywordChip = styled(Chip)({
  backgroundColor: '#EFEFEF',
  borderRadius: '8px',
  fontSize: '14px',
  fontWeight: 500,
  color: '#262626',
  marginTop: '8px',
});

const NavigationContainer = styled(Box)({
  marginTop: 'auto',
  display: 'flex',
  gap: '12px',
  paddingTop: '24px',
  borderTop: '1px solid #DBDBDB',
});

const SecondaryButton = styled(Button)({
  color: '#262626',
  fontSize: '16px',
  fontWeight: 600,
  padding: '12px 24px',
  border: '1px solid #DBDBDB',
  borderRadius: '8px',
  backgroundColor: '#FFFFFF',
  '&:hover': {
    backgroundColor: '#F8F9FA',
    borderColor: '#262626',
  },
});

const PrimaryButton = styled(Button)({
  background: 'linear-gradient(45deg, #4CB5F9, #B32EFF)',
  color: '#FFFFFF',
  fontSize: '16px',
  fontWeight: 600,
  padding: '12px 24px',
  borderRadius: '8px',
  border: 'none',
  '&:hover': {
    background: 'linear-gradient(45deg, #3AA4E8, #A21EE6)',
  },
  '&:disabled': {
    background: '#DBDBDB',
    color: '#8E8E8E',
  },
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

interface SidebarProps {
  step: number;
  selectedPost: any;
  keyword: string;
  dmMessage: string;
  posts: any[];
  onPostSelect: (post: any) => void;
  onKeywordChange: (keyword: string) => void;
  onDMMessageChange: (message: string) => void;
  onNext: () => void;
  onBack: () => void;
  canProceed: boolean;
}

const Sidebar: React.FC<SidebarProps> = ({
  step,
  selectedPost,
  keyword,
  dmMessage,
  posts,
  onPostSelect,
  onKeywordChange,
  onDMMessageChange,
  onNext,
  onBack,
  canProceed,
}) => {
  const [livePopupOpen, setLivePopupOpen] = useState(false);

  const handleGoLive = () => {
    setLivePopupOpen(true);
    onNext();
  };

  const handleCloseLivePopup = () => {
    setLivePopupOpen(false);
  };
  const renderStep1 = () => (
    <StepContainer>
      <StepTitle variant="h1"># When someone comments on</StepTitle>
      <RadioGroup value={selectedPost ? 'specific' : ''}>
        <RadioOption
          value="specific"
          control={<Radio />}
          label="a specific post or reel"
        />
      </RadioGroup>
      
      <Box sx={{ marginTop: '16px' }}>
        <Typography variant="body2" color="text.secondary" sx={{ marginBottom: '12px' }}>
          Select a post or reel:
        </Typography>
        <Grid container spacing={2}>
          {posts.map((post) => (
            <Grid item xs={6} key={post.id}>
              <PostCard
                selected={selectedPost?.id === post.id}
                onClick={() => onPostSelect(post)}
              >
                <CardContent sx={{ padding: '8px' }}>
                  <PostThumbnail src={post.thumbnail} alt={post.caption} />
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      fontWeight: 500, 
                      marginTop: '8px',
                      fontSize: '12px',
                      lineHeight: 1.3,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical'
                    }}
                  >
                    {post.caption}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '10px' }}>
                    {post.likes} likes • {post.comments} comments
                  </Typography>
                </CardContent>
              </PostCard>
            </Grid>
          ))}
        </Grid>
      </Box>
    </StepContainer>
  );

  const renderStep2 = () => (
    <StepContainer>
      <StepTitle variant="h2">## And this comment has</StepTitle>
      <RadioGroup value="specific">
        <RadioOption
          value="specific"
          control={<Radio />}
          label="a specific word or words"
        />
      </RadioGroup>
      
      <Box sx={{ marginTop: '16px' }}>
        <TextField
          fullWidth
          placeholder="Enter keyword (e.g., Price)"
          value={keyword}
          onChange={(e) => onKeywordChange(e.target.value)}
          variant="outlined"
          size="small"
        />
        {keyword && (
          <KeywordChip
            label={`${keyword}: 1`}
            sx={{ marginTop: '8px' }}
          />
        )}
        <Typography variant="body2" color="text.secondary" sx={{ marginTop: '8px' }}>
          Use comma to separate words
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
          For example: (Price) (Link) (Shop)
        </Typography>
      </Box>
    </StepContainer>
  );

  const renderStep3 = () => (
    <StepContainer>
      <StepTitle variant="h2">## They will get</StepTitle>
      
      <Box sx={{ marginBottom: '24px' }}>
        <Typography variant="body1" sx={{ fontWeight: 600, marginBottom: '12px' }}>
          an opening DM
        </Typography>
        
        <Box
          sx={{
            backgroundColor: '#F8F9FA',
            border: '1px solid #DBDBDB',
            borderRadius: '8px',
            padding: '16px',
            fontSize: '14px',
            lineHeight: 1.5,
            color: '#262626',
            whiteSpace: 'pre-wrap',
            marginBottom: '12px',
          }}
        >
          {dmMessage || "Hey! I'm so happy you're here, thanks so much for your interest 😊\n\nClick below and I'll send you the link in just a sec :\n\n[Send me the link]"}
        </Box>
        
        <Button
          color="primary"
          sx={{ padding: '8px 0', minWidth: 'auto', textTransform: 'none' }}
        >
          Add A Link
        </Button>
      </Box>
      
      <TextField
        fullWidth
        multiline
        rows={6}
        placeholder="Type your opening DM message here..."
        value={dmMessage}
        onChange={(e) => onDMMessageChange(e.target.value)}
        variant="outlined"
      />
      
      <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'right', marginTop: '4px' }}>
        {dmMessage.length} characters
      </Typography>
    </StepContainer>
  );

  const renderCurrentStep = () => {
    switch (step) {
      case 1:
        return renderStep1();
      case 2:
        return renderStep2();
      case 3:
        return renderStep3();
      default:
        return null;
    }
  };

  return (
    <>
      <SidebarContainer>
        <SidebarHeader>
          <SidebarTitle>Create Workflow</SidebarTitle>
          <StepIndicator>
            <StepDot completed={step > 1} active={step === 1} />
            <StepDot completed={step > 2} active={step === 2} />
            <StepDot completed={step > 3} active={step === 3} />
          </StepIndicator>
        </SidebarHeader>
        
        <SidebarContent>
          {renderCurrentStep()}
          
          <NavigationContainer>
            {step > 1 && (
              <SecondaryButton onClick={onBack}>
                Back
              </SecondaryButton>
            )}
            
            {step < 3 && (
              <PrimaryButton
                onClick={onNext}
                disabled={!canProceed}
                sx={{ marginLeft: step === 1 ? 'auto' : '0' }}
              >
                Next
              </PrimaryButton>
            )}
            
            {step === 3 && (
              <PrimaryButton
                onClick={handleGoLive}
                disabled={!canProceed}
                startIcon={<PlayArrowIcon />}
                sx={{ marginLeft: 'auto' }}
              >
                Go Live
              </PrimaryButton>
            )}
          </NavigationContainer>
        </SidebarContent>
      </SidebarContainer>

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
    </>
  );
};

export default Sidebar; 