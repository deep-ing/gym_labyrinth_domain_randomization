from os import system
import gym 
import pybullet as p
from gym_domain_randomizer.maps import GridMap1
from gym_domain_randomizer.PhysicalEnv import PhysicalEnv
import numpy as np 
import pybullet_data 


AGENT_INFO = {
        "globalScaling" : 0.5,
        "acc" : 2.0,
        "max_speed" : 10,
        # "color" : [0,125,0,1]
    }

OBSTACLE_INFO = {"globalScaling" : 20,
        "color" : [0,0,0,0.9],
        "acc" : 0.0001,
        "max_speed" : 2}

MAP_SIZE = 10 

class Labyrinth(PhysicalEnv):
    def __init__(self, 
                connect_gui=False, 
                random_agent_pos=7, 
                physical_steps=10, 
                system_random_interval=[[(0,0.1)], # list of the first  interval
                                        [(0,1)], # list of the second interval
                                        [(0,0.1)],
                                        [(0,0.1)],
                                        [(0,0.1)],
                                        [(0,0.1)]]):
        
        super().__init__(MAP_SIZE, None, AGENT_INFO, OBSTACLE_INFO)
        
        # wind (2 theta, magnitude)  # friction (4 direction)
        self.set_system_params(np.zeros(6,))
        self.map = GridMap1()
        self.num_obstacles = self.map.num_obstacles
        self.physical_steps = physical_steps
        self.action_space = gym.spaces.Discrete(5) 
        self.system_random_interval = system_random_interval
        
        # TODO : define the observation space
        self.connect(connect_gui)
        self.random_agent_pos = random_agent_pos
        system_vector = self.get_random_system_params()
        self.set_system_params(system_vector)

        self.obs_info = {"width": 128, 
                         "height":128,
                         "fov" : 60,
                         "aspect" :1,
                         "near" : 0.02,
                         "far":11,
                         "renderer" : [p.ER_TINY_RENDERER, p.ER_BULLET_HARDWARE_OPENGL][0] }
        fov, aspect, near, far = (self.obs_info['fov'],
                                  self.obs_info['aspect'],
                                  self.obs_info['near'],
                                  self.obs_info['far'])
        
        self.obs_info['view_matrix'] = p.computeViewMatrix([0, 0, 11.0], [0, 0, 0], [0, 1, 0])
        self.obs_info['projection_matrix'] = p.computeProjectionMatrixFOV(fov, aspect, near, far)
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, shape=(4,self.obs_info['width'],self.obs_info['height'])) 
        
    def obs(self):
        images = p.getCameraImage(self.obs_info['width'],
                          self.obs_info['height'],
                          self.obs_info['view_matrix'],
                          self.obs_info['projection_matrix'],
                          renderer=self.obs_info['renderer'])

        obs = images[2].transpose(2,0,1)/255.0               
        return obs 
    
    
    def connect(self, connect_gui):
        if connect_gui:
            p.connect(p.GUI)            
        else:
            p.connect(p.DIRECT)    
            
    
    def get_random_system_params(self):
        system_vector = np.zeros(shape=(6,))
        for i, element in enumerate(self.system_random_interval):
            candidates = [] 
            for left, right in element:
                candidates.append(np.random.uniform(left, right))
            system_vector[i] = np.random.choice(candidates)
        
        return system_vector
    
    def set_system_params(self, system_vector):
        assert system_vector.shape == (6,)
        self.system_vector = system_vector
    
    def apply_system_params(self, agent):
        # wind effect 
        r, theta = self.system_vector[:2]
        x, y = (r*np.cos(2*np.pi*theta), r*np.sin(2*np.pi*theta))
        force = [x,y,0]
        p.applyExternalForce(agent.pid, -1, 
                            forceObj=force,
                            posObj=agent.position,
                            flags=p.WORLD_FRAME) 
        # directional friction 
        agent.direction_friction = self.system_vector[2:]
        # ======================
        
    def reset(self):
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        if self.objects:
            for object_type, object_list in self.objects.items():
                for obj in object_list:
                    obj.remove()
                object_list.clear()
        for _ in range(0): # no target
            self.build_position("target", [t-i for t,i in zip(self.map.target_position, self.map.init_position)] , **self.target_info)
        for _ in range(1): # only single agent
            # Randomly starts at the left line
            self.build_position("agent",  [a-i for a,i in zip(self.map.agent_position + np.array([0,-self.random_agent_pos*np.random.random(),0 ]), self.map.init_position)], **self.agent_info)
        for r in range(self.map.width):
            for c in range(self.map.height):
                if self.map.map1[r][c] == 1:
                    self.build_position("obstacle", [r-self.map.init_position[0], c-self.map.init_position[1] ,0], **self.obstacle_info)
        for obj in self.objects["obstacle"]:
            p.changeDynamics(obj.pid, -1, mass=100000)
        return self.obs()

    def step(self, agent_action):
        agent= self.objects['agent'][0]
        self.apply_system_params(agent)
        agent.take_action(agent_action)     
        # Apply system parameters        
        for i in range(self.physical_steps):
            p.stepSimulation()
        for object_type, object_list in self.objects.items():
            for obj in object_list:
                if obj.alive:
                    obj.update()
                    obj.decrease_velocity()
                    obj.clip_velocity()


        reward = self._reward(agent)
        done = self._done(agent)
        info = self._info()
        return self.obs(), reward, done, info

    def _reward(self, agent): 
        if agent.position[0] >2 and agent.position[1] < -3:
            reward = 0
        else:
            # time penalty
            reward =  - 0.1 
        return reward 

    def _done(self, agent):
        if agent.position[0] > 2 and agent.position[1] < -3:
            done = True
        else:
            done = False
        return done
         
    def _info(self):
        return {}
