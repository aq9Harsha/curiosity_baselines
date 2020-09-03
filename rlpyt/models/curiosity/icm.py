
import torch
from torch import nn

from rlpyt.utils.tensor import infer_leading_dims, restore_leading_dims
from rlpyt.models.utils import Flatten

class UniverseHead(nn.Module):
    '''
    Universe agent example: https://github.com/openai/universe-starter-agent
    '''
    def __init__(
            self, 
            image_shape,
            batch_norm=False
            ):
        super(UniverseHead, self).__init__()
        c, h, w = image_shape
        sequence = list()
        for l in range(5):
            if l == 0:
                conv = nn.Conv2d(in_channels=c, out_channels=32, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1))
            else:
                conv = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1))
            block = [conv, nn.ELU()]
            if batch_norm:
                block.append(nn.BatchNorm2d(32))
            sequence.extend(block)
        self.model = nn.Sequential(*sequence)


    def forward(self, state):
        """Compute the feature encoding convolution + head on the input;
        assumes correct input shape: [B,C,H,W]."""
        encoded_state = self.model(state)
        return encoded_state.view(encoded_state.shape[0], -1)

class MazeHead(nn.Module):
    '''
    World discovery models paper
    '''
    def __init__(
            self, 
            image_shape,
            output_size=256,
            conv_output_size=256,
            batch_norm=False,
            ):
        super(MazeHead, self).__init__()
        c, h, w = image_shape
        self.output_size = output_size
        self.conv_output_size = conv_output_size
        sequence = [nn.Conv2d(in_channels=c, out_channels=16, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1)), 
                 nn.ReLU()]
        nn.init.kaiming_uniform(sequence[0].weight)
        sequence += [nn.Conv2d(in_channels=16, out_channels=16, kernel_size=(3, 3), stride=(2, 2), padding=(2, 2)),
                     nn.ReLU()]
        nn.init.kaiming_uniform(sequence[2].weight)
        sequence += [Flatten(),
                     nn.Linear(in_features=self.conv_output_size, out_features=self.output_size),
                     nn.ReLU()]
        self.model = nn.Sequential(*sequence)
        # self.model = nn.Sequential(
        #                         nn.Conv2d(in_channels=c, out_channels=16, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1)),
        #                         nn.ReLU(),
        #                         nn.Conv2d(in_channels=16, out_channels=16, kernel_size=(3, 3), stride=(2, 2), padding=(2, 2)),
        #                         nn.ReLU(),
        #                         Flatten(),
        #                         nn.Linear(in_features=self.conv_output_size, out_features=self.output_size),
        #                         nn.ReLU()
        #                         )

    def forward(self, state):
        """Compute the feature encoding convolution + head on the input;
        assumes correct input shape: [B,C,H,W]."""
        encoded_state = self.model(state)
        return encoded_state

class BurdaHead(nn.Module):
    '''
    Large scale curiosity paper
    '''
    def __init__(
            self, 
            image_shape,
            output_size=512,
            conv_output_size=3136,
            batch_norm=False,
            ):
        super(BurdaHead, self).__init__()
        c, h, w = image_shape
        self.output_size = output_size
        self.conv_output_size = conv_output_size
        sequence = list()
        sequence += [nn.Conv2d(in_channels=c, out_channels=32, kernel_size=(8, 8), stride=(4, 4)), 
                     nn.LeakyReLU()]
        if batch_norm:
            sequence.append(nn.BatchNorm2d(32))
        sequence += [nn.Conv2d(in_channels=32, out_channels=64, kernel_size=(4, 4), stride=(2, 2)), 
                     nn.LeakyReLU()]
        if batch_norm:
            sequence.append(nn.BatchNorm2d(64))
        sequence += [nn.Conv2d(in_channels=64, out_channels=64, kernel_size=(3, 3), stride=(1, 1)),
                     nn.LeakyReLU()]
        if batch_norm:
            sequence.append(nn.BatchNorm2d(64))
        sequence.append(Flatten())
        sequence.append(nn.Linear(in_features=self.conv_output_size, out_features=self.output_size))

        nn.init.xavier_uniform(sequence[0].weight) # xavier uniform conv layers
        nn.init.xavier_uniform(sequence[3].weight)
        nn.init.xavier_uniform(sequence[6].weight)

        self.model = nn.Sequential(*sequence)
        # self.model = nn.Sequential(
        #                         nn.Conv2d(in_channels=c, out_channels=32, kernel_size=(8, 8), stride=(4, 4)),
        #                         nn.LeakyReLU(),
        #                         # nn.BatchNorm2d(32),
        #                         nn.Conv2d(in_channels=32, out_channels=64, kernel_size=(4, 4), stride=(2, 2)),
        #                         nn.LeakyReLU(),
        #                         # nn.BatchNorm2d(64),
        #                         nn.Conv2d(in_channels=64, out_channels=64, kernel_size=(3, 3), stride=(1, 1)),
        #                         nn.LeakyReLU(),
        #                         # nn.BatchNorm2d(64),
        #                         Flatten(),
        #                         nn.Linear(in_features=self.conv_output_size, out_features=self.output_size),
        #                         # nn.BatchNorm1d(self.output_size)
        #                         )

    def forward(self, state):
        """Compute the feature encoding convolution + head on the input;
        assumes correct input shape: [B,C,H,W]."""
        encoded_state = self.model(state)
        return encoded_state

class ResBlock(nn.Module):
    def __init__(self,
                 feature_size,
                 action_size):
        super(ResBlock, self).__init__()

        self.lin_1 = nn.Linear(feature_size + action_size, feature_size)
        self.lin_2 = nn.Linear(feature_size + action_size, feature_size)

    def forward(self, x, action):
        res = nn.functional.leaky_relu(self.lin_1(torch.cat([x, action], 2)))
        res = self.lin_2(torch.cat([res, action], 2))
        return res + x

class ResForward(nn.Module):
    def __init__(self,
                 feature_size,
                 action_size):
        super(ResForward, self).__init__()

        self.lin_1 = nn.Linear(feature_size + action_size, feature_size)
        self.res_block_1 = ResBlock(feature_size, action_size)
        self.res_block_2 = ResBlock(feature_size, action_size)
        self.res_block_3 = ResBlock(feature_size, action_size)
        self.res_block_4 = ResBlock(feature_size, action_size)
        self.lin_last = nn.Linear(feature_size + action_size, feature_size)

    def forward(self, phi1, action):
        x = nn.functional.leaky_relu(self.lin_1(torch.cat([phi1, action], 2)))
        x = self.res_block_1(x, action)
        x = self.res_block_2(x, action)
        x = self.res_block_3(x, action)
        x = self.res_block_4(x, action)
        x = self.lin_last(torch.cat([x, action], 2))
        return x

class ICM(nn.Module):

    def __init__(
            self, 
            image_shape, 
            action_size, 
            feature_encoding='idf', 
            batch_norm=False,
            prediction_beta=0.01,
            obs_stats=None
            ):
        super(ICM, self).__init__()

        self.prediction_beta = prediction_beta
        self.feature_encoding = feature_encoding
        self.obs_stats = obs_stats
        if self.obs_stats is not None:
            self.obs_mean, self.obs_std = self.obs_stats

        if self.feature_encoding != 'none':
            if self.feature_encoding == 'idf':
                self.feature_size = 288
                self.encoder = UniverseHead(image_shape=image_shape, batch_norm=batch_norm)
            elif self.feature_encoding == 'idf_burda':
                self.feature_size = 512
                self.encoder = BurdaHead(image_shape=image_shape, output_size=self.feature_size, batch_norm=batch_norm)
            elif self.feature_encoding == 'idf_maze':
                self.feature_size = 256
                self.encoder = MazeHead(image_shape=image_shape, output_size=self.feature_size, batch_norm=batch_norm)

        # self.forward_model = nn.Sequential(
        #     nn.Linear(self.feature_size + action_size, 256),
        #     nn.ReLU(),
        #     nn.Linear(256, self.feature_size)
        #     )
        self.forward_model = ResForward(feature_size=self.feature_size,
                                        action_size=action_size)

        self.inverse_model = nn.Sequential(
            nn.Linear(self.feature_size * 2, self.feature_size),
            nn.ReLU(),
            nn.Linear(self.feature_size, action_size)
            )


    def forward(self, obs1, obs2, action):

        if self.obs_stats is not None:
            img1 = (obs1 - self.obs_mean) / self.obs_std
            img2 = (obs2 - self.obs_mean) / self.obs_std

        img1 = obs1.type(torch.float)
        img2 = obs2.type(torch.float) # Expect torch.uint8 inputs

        # Infer (presence of) leading dimensions: [T,B], [B], or [].
        # lead_dim is just number of leading dimensions: e.g. [T, B] = 2 or [] = 0.
        lead_dim, T, B, img_shape = infer_leading_dims(obs1, 3) 

        phi1 = img1
        phi2 = img2
        if self.feature_encoding != 'none':
            phi1 = self.encoder(img1.view(T * B, *img_shape))
            phi2 = self.encoder(img2.view(T * B, *img_shape))
            phi1 = phi1.view(T, B, -1) # make sure you're not mixing data up here
            phi2 = phi2.view(T, B, -1)

        # predicted_action = nn.functional.softmax(self.inverse_model(torch.cat([phi1.view(T, B, -1), phi2.view(T, B, -1)], 2)), dim=-1) # SOFTMAX IS PERFORMED INSIDE CROSS ENT
        predicted_action = self.inverse_model(torch.cat([phi1, phi2], 2))

        # predicted_phi2 = self.forward_model(torch.cat([phi1.detach(), action.view(T, B, -1)], 2)) # USED WITH OLD FORWARD MODEL
        predicted_phi2 = self.forward_model(phi1.detach(), action.view(T, B, -1))

        return phi1, phi2, predicted_phi2, predicted_action

    def compute_bonus(self, obs, action, next_obs):
        phi1, phi2, predicted_phi2, predicted_action =  self.forward(obs, next_obs, action)
        forward_loss = 0.5 * (nn.functional.mse_loss(predicted_phi2, phi2, reduction='none').sum(-1)/self.feature_size)
        return self.prediction_beta * forward_loss

    def compute_loss(self, obs, action, next_obs):
        #------------------------------------------------------------#
        # hacky dimension add for when you have only one environment
        if action.dim() == 2: 
            action = action.unsqueeze(1)
        #------------------------------------------------------------#
        phi1, phi2, predicted_phi2, predicted_action = self.forward(obs, next_obs, action)
        action = torch.max(action.view(-1, *action.shape[2:]), 1)[1] # conver action to (T * B, action_size), then get target indexes
        inverse_loss = nn.functional.cross_entropy(predicted_action.view(-1, *predicted_action.shape[2:]), action.detach())
        forward_loss = 0.5 * nn.functional.mse_loss(predicted_phi2, phi2.detach())
        return inverse_loss.squeeze(), forward_loss.squeeze()





